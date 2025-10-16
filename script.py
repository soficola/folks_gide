import os
import json
import time
import logging
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from web3.types import LogReceipt

# --- Configuration Loading ---
loud_dotenv() # Load environment variables from .env file

# --- Basic Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('BridgeListener')


class ChainConnector:
    """
    Manages the connection to a single blockchain node via RPC.
    It encapsulates the Web3.py instance and provides basic interaction methods.
    """
    def __init__(self, rpc_url: str, chain_id: int):
        """
        Initializes the connector with blockchain-specific details.
        
        Args:
            rpc_url (str): The RPC endpoint URL for the blockchain node.
            chain_id (int): The chain ID of the blockchain.
        """
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.w3: Optional[Web3] = None
        self.logger = logging.getLogger(f'ChainConnector-{self.chain_id}')

    def connect(self) -> None:
        """
        Establishes a connection to the blockchain node.
        Injects PoA middleware for compatibility with chains like BSC or Polygon.
        Raises ConnectionError on failure.
        """
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            # Inject middleware for PoA chains (e.g., BSC, Polygon, Goerli)
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            if not self.is_connected():
                raise ConnectionError(f"Failed to connect to chain {self.chain_id} at {self.rpc_url}")
            
            self.logger.info(f"Successfully connected to chain {self.chain_id}. Latest block: {self.get_latest_block()}")
        except Exception as e:
            self.logger.error(f"Connection error for chain {self.chain_id}: {e}")
            raise ConnectionError(f"Could not connect to {self.rpc_url}") from e

    def is_connected(self) -> bool:
        """Checks if the Web3 instance is connected to the node."""
        return self.w3 is not None and self.w3.is_connected()

    def get_latest_block(self) -> int:
        """Retrieves the latest block number from the connected chain."""
        if self.is_connected():
            return self.w3.eth.block_number
        return -1

    def get_contract(self, address: str, abi: Dict) -> Contract:
        """Returns a Web3.py contract instance."""
        if not self.is_connected():
            raise ConnectionError("Not connected to any chain.")
        checksum_address = Web3.to_checksum_address(address)
        return self.w3.eth.contract(address=checksum_address, abi=abi)


class BridgeEventHandler:
    """
    Handles the business logic for processing events detected by the listener.
    This includes validation, data transformation, and triggering actions on the destination chain.
    """
    
    # A mock price oracle API for demonstration purposes
    MOCK_ORACLE_API = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"

    def __init__(self, dest_chain_connector: ChainConnector, dest_contract: Contract, validator_address: str):
        """
        Initializes the event handler.
        
        Args:
            dest_chain_connector (ChainConnector): The connector for the destination chain.
            dest_contract (Contract): The bridge contract instance on the destination chain.
            validator_address (str): The address of this validator node, used for signing.
        """
        self.dest_chain_connector = dest_chain_connector
        self.dest_contract = dest_contract
        self.validator_address = validator_address
        self.logger = logging.getLogger('EventHandler')

    def process_event(self, event: LogReceipt) -> None:
        """
        Main entry point for processing a raw event from the source chain.
        
        Args:
            event (LogReceipt): The event log data from web3.py.
        """
        self.logger.info(f"Processing event from transaction: {event['transactionHash'].hex()}")
        
        try:
            event_args = event['args']
            # Basic validation: ensure all required fields are present
            if not all(k in event_args for k in ['from', 'to', 'amount', 'nonce']):
                self.logger.warning(f"Malformed event detected, skipping. Data: {event_args}")
                return

            if not self._validate_transaction(event_args):
                self.logger.warning(f"Transaction validation failed for nonce {event_args['nonce']}. Skipping.")
                return

            self.logger.info(f"Validation successful for nonce {event_args['nonce']}.")
            self._simulate_mint_transaction(event_args)

        except Exception as e:
            self.logger.error(f"An unexpected error occurred while processing event: {event}. Error: {e}", exc_info=True)

    def _validate_transaction(self, tx_details: Dict[str, Any]) -> bool:
        """
        Performs validation checks on the transaction details from the event.
        This is a simulation and includes checks like minimum amount and a mock API call.
        
        Returns:
            bool: True if the transaction is valid, False otherwise.
        """
        # Rule 1: Amount must be greater than a certain threshold
        min_transfer_amount = 10000000000000000  # 0.01 tokens in wei
        if tx_details['amount'] < min_transfer_amount:
            self.logger.warning(f"Validation failed: Amount {tx_details['amount']} is below threshold {min_transfer_amount}")
            return False

        # Rule 2: Simulate checking against an external service (e.g., risk scoring, price oracle)
        try:
            response = requests.get(self.MOCK_ORACLE_API, timeout=5)
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
            price_data = response.json()
            usd_price = price_data.get('ethereum', {}).get('usd', 0)
            if usd_price < 1000: # Arbitrary rule: do not process if ETH price is too low
                self.logger.warning(f"Validation failed: Market price ${usd_price} is below processing threshold.")
                return False
            self.logger.info(f"External API check passed. Current ETH price: ${usd_price}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API call for validation failed: {e}. Approving transaction as a fallback.")
            # In a real system, you might want to fail-safe or retry
        
        return True

    def _simulate_mint_transaction(self, mint_details: Dict[str, Any]) -> None:
        """
        Simulates building and sending the minting transaction to the destination chain.
        In a real implementation, this would involve signing and sending a real transaction.
        """
        if not self.dest_chain_connector.is_connected():
            self.logger.error("Cannot simulate mint transaction: destination chain is not connected.")
            return
        
        w3 = self.dest_chain_connector.w3
        recipient = mint_details['to']
        amount = mint_details['amount']
        source_nonce = mint_details['nonce']

        self.logger.info(f"Simulating mint of {amount} tokens for {recipient} on chain {self.dest_chain_connector.chain_id}")
        
        # --- This is where the real transaction logic would go ---
        # 1. Check if this nonce has already been processed to prevent replay attacks.
        # has_processed = self.dest_contract.functions.processedNonces(source_nonce).call()
        # if has_processed:
        #     self.logger.warning(f"Nonce {source_nonce} has already been processed. Skipping.")
        #     return

        # 2. Build the transaction
        # private_key = os.getenv('VALIDATOR_PRIVATE_KEY')
        # tx = self.dest_contract.functions.mint(recipient, amount, source_nonce).build_transaction({
        #     'from': self.validator_address,
        #     'chainId': self.dest_chain_connector.chain_id,
        #     'gas': 200000,
        #     'gasPrice': w3.eth.gas_price,
        #     'nonce': w3.eth.get_transaction_count(self.validator_address)
        # })
        
        # 3. Sign the transaction
        # signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)
        
        # 4. Send the transaction
        # tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        # self.logger.info(f"Transaction sent to destination chain. Hash: {tx_hash.hex()}")
        # --- End of real transaction logic ---
        
        print("\n" + "-" * 80)
        print(f"[SIMULATION] ACTION: MINT on Destination Chain")
        print(f"  - To: {recipient}")
        print(f"  - Amount: {amount} wei")
        print(f"  - Source Nonce: {source_nonce}")
        print(f"  - Validator: {self.validator_address}")
        print("-" * 80 + "\n")


class CrossChainEventListener:
    """
    The main orchestrator that listens for events on a source blockchain
    and uses a BridgeEventHandler to process them.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the listener with a comprehensive configuration.
        """
        self.config = config
        self.logger = logging.getLogger('EventListener')
        self._setup_components()

    def _setup_components(self) -> None:
        """
        Initializes and connects all necessary components based on the config.
        """
        self.logger.info("Setting up listener components...")
        
        # Setup for the source chain (where we listen for events)
        self.source_connector = ChainConnector(self.config['SOURCE_RPC'], self.config['SOURCE_CHAIN_ID'])
        self.source_connector.connect()
        self.source_contract = self.source_connector.get_contract(
            self.config['SOURCE_BRIDGE_CONTRACT'], json.loads(self.config['SOURCE_BRIDGE_ABI'])
        )

        # Setup for the destination chain (where we take action)
        self.dest_connector = ChainConnector(self.config['DEST_RPC'], self.config['DEST_CHAIN_ID'])
        self.dest_connector.connect()
        dest_contract = self.dest_connector.get_contract(
            self.config['DEST_BRIDGE_CONTRACT'], json.loads(self.config['DEST_BRIDGE_ABI'])
        )

        # Setup the event handler
        self.event_handler = BridgeEventHandler(
            self.dest_connector, dest_contract, self.config['VALIDATOR_ADDRESS']
        )
        
        self.logger.info("Component setup complete.")

    def listen_for_events(self) -> None:
        """
        Starts the main event listening loop.
        It polls the blockchain for new logs of the specified event.
        """
        event_name = self.config['EVENT_TO_LISTEN']
        self.logger.info(f"Starting to listen for '{event_name}' events on contract {self.source_contract.address}")

        # Create an event filter. It will only capture events from the point of its creation.
        event_filter = self.source_contract.events[event_name].create_filter(fromBlock='latest')

        while True:
            try:
                new_events = event_filter.get_new_entries()
                if not new_events:
                    self.logger.debug("No new events found. Polling again in a few seconds...")
                else:
                    self.logger.info(f"Found {len(new_events)} new event(s)!")
                    for event in new_events:
                        self.event_handler.process_event(event)
                
                time.sleep(self.config.get('POLLING_INTERVAL', 10))
            
            except Exception as e:
                self.logger.error(f"Error in listening loop: {e}. Reconnecting and retrying...", exc_info=True)
                # Simple reconnection logic
                time.sleep(15)
                self._setup_components()
                event_filter = self.source_contract.events[event_name].create_filter(fromBlock='latest')

    def run(self) -> None:
        """
        Public method to start the listener service.
        """
        try:
            self.listen_for_events()
        except KeyboardInterrupt:
            self.logger.info("Shutdown signal received. Exiting gracefully.")
        except Exception as e:
            self.logger.critical(f"A critical error forced the listener to stop: {e}", exc_info=True)


def get_default_config() -> Dict[str, Any]:
    """
    Provides a default configuration dictionary. In a real app, this would come from a config file or env vars.
    Using os.getenv() allows overriding with a .env file.
    """
    # A simple ABI for a 'TokensLocked' event for demonstration purposes
    source_abi = '''
    [{
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": true, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": false, "internalType": "uint256", "name": "nonce", "type": "uint256"}
        ],
        "name": "TokensLocked",
        "type": "event"
    }]
    '''
    # A simple ABI for a 'mint' function for demonstration purposes
    dest_abi = '''
    [{
        "inputs": [
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "uint256", "name": "sourceNonce", "type": "uint256"}
        ],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }]
    '''
    
    return {
        # Source Chain (e.g., Ethereum Mainnet or Goerli Testnet)
        'SOURCE_CHAIN_ID': int(os.getenv('SOURCE_CHAIN_ID', '5')),
        'SOURCE_RPC': os.getenv('SOURCE_RPC', 'https://goerli.infura.io/v3/your_infura_id'),
        'SOURCE_BRIDGE_CONTRACT': os.getenv('SOURCE_BRIDGE_CONTRACT', '0xSourceBridgeContractAddress'),
        'SOURCE_BRIDGE_ABI': os.getenv('SOURCE_BRIDGE_ABI', source_abi),
        
        # Destination Chain (e.g., Polygon Mainnet or Mumbai Testnet)
        'DEST_CHAIN_ID': int(os.getenv('DEST_CHAIN_ID', '80001')),
        'DEST_RPC': os.getenv('DEST_RPC', 'https://polygon-mumbai.infura.io/v3/your_infura_id'),
        'DEST_BRIDGE_CONTRACT': os.getenv('DEST_BRIDGE_CONTRACT', '0xDestinationBridgeContractAddress'),
        'DEST_BRIDGE_ABI': os.getenv('DEST_BRIDGE_ABI', dest_abi),
        
        # Listener Configuration
        'EVENT_TO_LISTEN': os.getenv('EVENT_TO_LISTEN', 'TokensLocked'),
        'POLLING_INTERVAL': int(os.getenv('POLLING_INTERVAL', '12')), # In seconds
        
        # Validator Configuration
        'VALIDATOR_ADDRESS': os.getenv('VALIDATOR_ADDRESS', '0xValidatorWalletAddress'),
        'VALIDATOR_PRIVATE_KEY': os.getenv('VALIDATOR_PRIVATE_KEY', 'your_private_key_here'), # WARNING: For simulation only!
    }

if __name__ == '__main__':
    logger.info("Starting Cross-Chain Bridge Event Listener...")
    
    config = get_default_config()
    
    # A simple check to ensure user has changed default placeholder values
    if 'your_infura_id' in config['SOURCE_RPC'] or 'your_infura_id' in config['DEST_RPC']:
        logger.error("Please replace 'your_infura_id' in your .env file or script configuration.")
    elif '0x' not in config['VALIDATOR_ADDRESS'] or len(config['VALIDATOR_ADDRESS']) != 42:
         logger.error("Please provide a valid validator address in your .env file or script configuration.")
    else:
        try:
            listener = CrossChainEventListener(config)
            listener.run()
        except ConnectionError as e:
            logger.critical(f"Failed to establish initial blockchain connection: {e}. Please check your RPC URLs and network.")
        except Exception as e:
            logger.critical(f"An unhandled exception occurred during initialization: {e}", exc_info=True)

# @-internal-utility-start
CACHE = {}
def get_from_cache_3795(key: str):
    """Retrieves an item from cache. Implemented on 2025-10-16 17:48:53"""
    return CACHE.get(key, None)
# @-internal-utility-end

