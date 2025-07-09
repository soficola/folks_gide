# {repo_name}

A sophisticated Python-based simulation of a cross-chain bridge event listener. This project is designed as an architectural showcase, demonstrating how a robust, modular, and scalable off-chain component for a decentralized system can be built.

It simulates a validator node that listens for `TokensLocked` events on a source blockchain and triggers a corresponding `mint` action on a destination blockchain.

## Concept

In a typical cross-chain bridge, users lock assets in a smart contract on Chain A. Off-chain validators (or listeners) detect this event, validate it, and then collectively sign a message to authorize the minting of an equivalent wrapped asset on Chain B. This script simulates the core logic of one such validator.

**The key functions are:**
1.  **Connect**: Establish and maintain connections to RPC nodes for both the source and destination chains.
2.  **Listen**: Continuously monitor the source chain's bridge contract for a specific event (e.g., `TokensLocked`).
3.  **Validate**: Upon detecting an event, perform a series of validation checks. This can include checking the transaction amount, verifying addresses, or even consulting external APIs like price oracles.
4.  **Act**: If validation passes, construct, sign, and broadcast a transaction to the destination chain's bridge contract to complete the cross-chain transfer (e.g., by minting tokens).

This simulation focuses on the connection, listening, and validation steps, and prints a detailed summary of the action it *would* take on the destination chain.

## Code Architecture

The script is designed with a clear separation of concerns, making it easier to maintain, test, and extend.

-   `script.py`: The main entry point. It handles configuration loading, instantiates the main `CrossChainEventListener`, and starts the process.

-   `ChainConnector`: A dedicated class for managing the connection to a single blockchain. It encapsulates the `web3.py` instance and handles connection logic, including adding middleware for PoA chains. This allows the main listener to be chain-agnostic.

-   `CrossChainEventListener`: The central orchestrator. It initializes and manages the `ChainConnector` instances for both source and destination chains. Its primary role is to run the main polling loop, catch events, and delegate their processing to the `BridgeEventHandler`.

-   `BridgeEventHandler`: This class contains all the business logic. When the listener passes it an event, this handler is responsible for:
    -   Parsing the event data.
    -   Performing complex validation (e.g., checking against business rules or external data sources via API calls).
    -   Simulating the final action on the destination chain.
    By isolating this logic, we can easily change the bridge's rules without touching the connection or listening code.

### Data Flow Diagram

```
[Source Chain] ----(RPC Call)---> [ChainConnector A]
      ^
      | emits event
      |
[Bridge Contract A]
      |
      | event detected by
      v
[CrossChainEventListener]
      |
      | passes event to
      v
[BridgeEventHandler]
      |
      | 1. Validates event (e.g., checks amount)
      | 2. Calls external API (e.g., Price Oracle) for extra validation
      | 3. Simulates transaction for Chain B
      v
[ChainConnector B] ---(Simulated RPC Call)---> [Destination Chain]
```

## How it Works

1.  **Initialization**: On startup, the script loads configuration from a `.env` file. This includes RPC URLs, contract addresses, and a validator wallet address.
2.  **Connection**: The `CrossChainEventListener` creates two instances of `ChainConnector`, one for the source chain and one for the destination. Each connector establishes a connection to its respective RPC endpoint.
3.  **Filtering**: The listener sets up an event filter on the source bridge contract using `web3.py`. It specifies the event name to watch (e.g., `TokensLocked`) and starts polling from the latest block.
4.  **Polling Loop**: The listener enters an infinite loop, periodically querying the filter for new event logs. A configurable polling interval prevents RPC rate-limiting.
5.  **Event Detection**: When one or more new events are found, the listener iterates through them.
6.  **Processing**: Each event log is passed to the `BridgeEventHandler`'s `process_event` method.
7.  **Validation**: The handler first decodes the event arguments (like `from`, `to`, `amount`). It then runs a series of checks:
    -   Internal check: Is the amount greater than the configured minimum?
    -   External check: It makes a `requests` call to the CoinGecko API (as a mock oracle) to fetch the current price of ETH and validates it against a threshold.
8.  **Action Simulation**: If all checks pass, the handler simulates the final step. It logs a detailed message outlining the `mint` transaction it would build and send to the destination chain, including the recipient, amount, and source transaction nonce.
9.  **Error Handling**: The application includes error handling for RPC connection failures and a graceful shutdown mechanism on `Ctrl+C`.

## Setup and Usage

### Prerequisites
-   Python 3.8+
-   Access to RPC endpoints for two EVM-compatible chains (e.g., from Infura, Alchemy, or a local node). For testing, you can use testnets like Goerli and Polygon Mumbai.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd {repo_name}
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows
    # venv\Scripts\activate
    # On macOS/Linux
    # source venv/bin/activate
    ```

3.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  **Create a `.env` file** in the root directory of the project by copying the example:
    ```bash
    # Create an empty .env file or copy an example if provided
    # On Windows: copy .env.example .env
    # On macOS/Linux: cp .env.example .env
    ```

2.  **Edit the `.env` file** with your specific details. You will need to provide your RPC URLs and placeholder addresses.

    ```ini
    # .env file content

    # Source Chain (e.g., Goerli Testnet)
    SOURCE_CHAIN_ID=5
    SOURCE_RPC="https://goerli.infura.io/v3/YOUR_INFURA_PROJECT_ID"
    SOURCE_BRIDGE_CONTRACT="0x0000000000000000000000000000000000000001" # Replace with a real contract address that emits the event

    # Destination Chain (e.g., Polygon Mumbai Testnet)
    DEST_CHAIN_ID=80001
    DEST_RPC="https://polygon-mumbai.infura.io/v3/YOUR_INFURA_PROJECT_ID"
    DEST_BRIDGE_CONTRACT="0x0000000000000000000000000000000000000002" # Replace with your destination contract address

    # Listener and Validator Config
    POLLING_INTERVAL=15
    VALIDATOR_ADDRESS="0xYourValidatorWalletAddressHere0000000000000"
    # The private key is not used in this simulation but would be required for a real implementation
    VALIDATOR_PRIVATE_KEY="0xyour_private_key_for_signing_transactions"
    ```

### Running the Script

Execute the main script from your terminal:

```bash
python script.py
```

The listener will start, connect to the chains, and begin polling for events. To test it, you would need to trigger the `TokensLocked` event on the source contract.

### Example Output

Here is what you might see in the console when the script detects and processes an event:

```
2023-10-27 10:30:00 - INFO - [BridgeListener] - Starting Cross-Chain Bridge Event Listener...
2023-10-27 10:30:01 - INFO - [EventListener] - Setting up listener components...
2023-10-27 10:30:02 - INFO - [ChainConnector-5] - Successfully connected to chain 5. Latest block: 9876543
2023-10-27 10:30:03 - INFO - [ChainConnector-80001] - Successfully connected to chain 80001. Latest block: 41234567
2023-10-27 10:30:03 - INFO - [EventListener] - Component setup complete.
2023-10-27 10:30:03 - INFO - [EventListener] - Starting to listen for 'TokensLocked' events on contract 0x0000000000000000000000000000000000000001
2023-10-27 10:30:18 - INFO - [EventListener] - Found 1 new event(s)!
2023-10-27 10:30:18 - INFO - [EventHandler] - Processing event from transaction: 0x123abc...def456
2023-10-27 10:30:19 - INFO - [EventHandler] - External API check passed. Current ETH price: $1580.5
2023-10-27 10:30:19 - INFO - [EventHandler] - Validation successful for nonce 123.
2023-10-27 10:30:19 - INFO - [EventHandler] - Simulating mint of 5000000000000000000 tokens for 0xRecipientAddress... on chain 80001

--------------------------------------------------------------------------------
[SIMULATION] ACTION: MINT on Destination Chain
  - To: 0xRecipientAddress...
  - Amount: 5000000000000000000 wei
  - Source Nonce: 123
  - Validator: 0xYourValidatorWalletAddressHere0000000000000
--------------------------------------------------------------------------------

```
