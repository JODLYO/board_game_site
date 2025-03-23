let selectedCards = [];
let playerIds = null;
let sessionId = null;
let currentGameState = null; // Add this line
const lobbyId = document.getElementById('lobby-id').dataset.lobbyId;
const currentUsername = document.getElementById('current-username').dataset.lobbyId;

// Function to handle card selection
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', () => {
        const cardId = card.getAttribute('data-card-id');
        if (selectedCards.includes(cardId)) {
            selectedCards = selectedCards.filter(id => id !== cardId);
            card.classList.remove('selected');
        } else {
            selectedCards.push(cardId);
            card.classList.add('selected');
        }
        monitorSelectedCards(); // Check set when 3 cards are selected
    });
});

// Monitor selectedCards array for changes
function monitorSelectedCards() {
    if (selectedCards.length === 3) {
        console.log('Automatically checking set');
        checkSet();
    }
}

// Function to send a player's move via WebSocket
function sendMove(username, cardIds) {
    if (isProcessingMove) {
        console.error('A move is already being processed.');
        return;
    }
    if (!sessionId) {
        console.error('Session ID is not set.');
        return;
    }
    if (!username) {
        console.error('Username is not set.');
        return;
    }

    // Validate card IDs against the current board state
    if (!currentGameState || !currentGameState.board) {
        console.error('Current game state or board is not defined.');
        return;
    }

    // Validate card IDs against the current board state
    const boardCardIds = Object.values(currentGameState.board);
    if (!cardIds.every(id => boardCardIds.includes(id))) {
        console.log(cardIds)
        console.log(boardCardIds)
        console.error('Invalid card IDs: not all cards are on the board.');
        return;
    }

    isProcessingMove = true;
    console.log('Sending make_move message:', {
        type: 'make_move',
        session_id: sessionId,
        username: username,
        card_ids: cardIds
    });
    gameSocket.send(JSON.stringify({
        'type': 'make_move',
        'session_id': sessionId,
        'username': username,
        'card_ids': cardIds
    }));
}

// Function to check if selected cards form a valid SET
function checkSet() {
    if (selectedCards.length !== 3) {
        document.getElementById('message').innerText = 'Please select exactly 3 cards.';
        return;
    }

    const cards = selectedCards.map(id => {
        const cardElement = document.querySelector(`.card[data-card-id="${id}"]`);
        if (!cardElement) {
            console.error(`Card with ID ${id} not found.`);
            return null;
        }
        return {
            number: parseInt(cardElement.getAttribute('data-number')),
            shading: cardElement.getAttribute('data-shading'),
            color: cardElement.getAttribute('data-color'),
            symbol: cardElement.getAttribute('data-symbol')
        };
    });

    // Check if any card is null
    if (cards.some(card => card === null)) {
        document.getElementById('message').innerText = 'Error: One or more cards not found.';
        return;
    }

    const isValid = isValidSet(cards);
    if (isValid) {
        document.getElementById('message').innerText = 'You found a valid set!';
        console.log('sending move');
        sendMove(currentUsername, selectedCards);
    } else {
        document.getElementById('message').innerText = 'Invalid set. Try again.';
    }

    // Reset selected cards
    selectedCards.forEach(cardId => {
        const cardElement = document.querySelector(`.card[data-card-id="${cardId}"]`);
        if (cardElement) {
            cardElement.classList.remove('selected');
        }
    });
    selectedCards = [];
}

// Function to validate if selected cards form a SET
function isValidSet(cards) {
    const numbers = new Set(cards.map(card => card.number));
    const symbols = new Set(cards.map(card => card.symbol));
    const shadings = new Set(cards.map(card => card.shading));
    const colors = new Set(cards.map(card => card.color));

    return (numbers.size === 1 || numbers.size === 3) &&
        (symbols.size === 1 || symbols.size === 3) &&
        (shadings.size === 1 || shadings.size === 3) &&
        (colors.size === 1 || colors.size === 3);
}

// WebSocket setup
let gameSocket = null;

function setupWebSocket() {
    if (gameSocket) {
        gameSocket.close();  // Close any existing socket before opening a new one
    }

    gameSocket = new WebSocket(
        'ws://' + window.location.host + '/ws/game/'
    );

    gameSocket.onopen = function () {
        // Function to send a message to start a new game
        function startGame(lobbyId) {
            gameSocket.send(JSON.stringify({
                'type': 'start_game',
                'lobby_id': lobbyId,  // Pass the lobby ID
            }));
        }

        // Example usage: Start a new game
        startGame(lobbyId);
    };

    gameSocket.onmessage = function (e) {
        const data = JSON.parse(e.data);
        console.log('WebSocket message received:', data);
    
        if (data.type === 'game_state') {
            currentGameState = data.state; // Update the current game state
            updateGameState(data.state);
            isProcessingMove = false; // Reset the flag after the state is updated
        } else if (data.type === 'game_started') {
            sessionId = data.session_id;
            playerIds = data.player_ids;
            console.log('Game started with session ID:', sessionId);
            console.log('Player IDs:', playerIds);
        } else if (data.type === 'game_over') {
            alert('Game over! No more sets are possible.');
        }
    };

    gameSocket.onclose = function (e) {
        console.error('Socket closed unexpectedly');
    };
}

setupWebSocket();

function updateGameState(state) {
    console.log('updateGameState called with state:', state);

    // Update the board
    const boardContainer = document.getElementById('game-board');
    boardContainer.innerHTML = '';  // Clear current board

    // Determine the number of columns based on the number of cards
    const numCards = Object.keys(state.board).length;
    const numColumns = numCards === 15 ? 5 : 4; // 5 columns for 15 cards, 4 columns for 12 cards

    // Update the grid layout
    boardContainer.style.gridTemplateColumns = `repeat(${numColumns}, 1fr)`;

    // Append cards to the board
    Object.entries(state.board).forEach(([pos, cardId]) => {
        const cardData = state.cards[cardId];
        if (!cardData) {
            console.error(`Card data not found for ID: ${cardId}`);
            return;
        }
        const cardElement = createCardElement(cardId, cardData);
        boardContainer.appendChild(cardElement);  // Append card to the board
    });

    // Update the scores
    const scoresContainer = document.getElementById('scores');
    scoresContainer.innerHTML = '';  // Clear current scores

    // Dynamically create score elements for each player
    Object.entries(state.scores).forEach(([playerId, score]) => {
        const scoreElement = document.createElement('div');
        scoreElement.id = `player-${playerId}-score`;
        scoreElement.innerText = `Player ${playerId}: ${score}`;
        scoresContainer.appendChild(scoreElement);
    });

    // Update the title with the current score
    const totalScore = Object.values(state.scores).reduce((a, b) => a + b, 0);
    // Clear the message
    document.getElementById('message').innerText = '';

    // // Create left and right score containers
    // const leftScore = document.createElement('div');
    // leftScore.id = 'left-score';
    // const rightScore = document.createElement('div');
    // rightScore.id = 'right-score';

    // // Add scores to left and right containers
    // const players = Object.entries(state.scores);
    // if (players.length > 0) {
    //     leftScore.innerText = `Player ${players[0][0]}: ${players[0][1]}`; // First player on the left
    // }
    // if (players.length > 1) {
    //     rightScore.innerText = `Player ${players[1][0]}: ${players[1][1]}`; // Second player on the right
    // }

    // // Append left and right scores to the scores container
    // scoresContainer.appendChild(leftScore);
    // scoresContainer.appendChild(rightScore);

    // // Update the title with the current score
    // const totalScore = Object.values(state.scores).reduce((a, b) => a + b, 0);
    // // Clear the message
    // document.getElementById('message').innerText = '';
}

function createCardElement(cardId, cardData) {
    const cardElement = document.createElement('div');
    cardElement.classList.add('card');
    cardElement.setAttribute('data-card-id', cardId);
    cardElement.setAttribute('data-number', cardData.number);
    cardElement.setAttribute('data-symbol', cardData.symbol);
    cardElement.setAttribute('data-shading', cardData.shading);
    cardElement.setAttribute('data-color', cardData.color);

    const cardContent = document.createElement('div');
    cardContent.classList.add('card-content');

    // Add symbols based on the number
    for (let i = 0; i < cardData.number; i++) {
        const symbol = document.createElement('div');
        symbol.classList.add('symbol', cardData.symbol.toLowerCase(), 'shading', cardData.shading.toLowerCase(), 'color', `color-${cardData.color.toLowerCase()}`);
        cardContent.appendChild(symbol);
    }

    cardElement.appendChild(cardContent);

    // Add click event listener to select cards
    cardElement.addEventListener('click', () => {
        const cardId = cardElement.getAttribute('data-card-id');
        if (selectedCards.includes(cardId)) {
            selectedCards = selectedCards.filter(id => id !== cardId);
            cardElement.classList.remove('selected');
        } else {
            selectedCards.push(cardId);
            cardElement.classList.add('selected');
        }
        monitorSelectedCards(); // Check set when 3 cards are selected
    });

    return cardElement;
}

function highlightSet() {
    // Get all card elements on the board
    const cards = Array.from(document.querySelectorAll('.card'));

    // Check all combinations of 3 cards
    for (let i = 0; i < cards.length - 2; i++) {
        for (let j = i + 1; j < cards.length - 1; j++) {
            for (let k = j + 1; k < cards.length; k++) {
                const card1 = cards[i];
                const card2 = cards[j];
                const card3 = cards[k];

                // Get the attributes of each card
                const card1Attributes = {
                    number: parseInt(card1.getAttribute('data-number')),
                    symbol: card1.getAttribute('data-symbol'),
                    shading: card1.getAttribute('data-shading'),
                    color: card1.getAttribute('data-color'),
                };
                const card2Attributes = {
                    number: parseInt(card2.getAttribute('data-number')),
                    symbol: card2.getAttribute('data-symbol'),
                    shading: card2.getAttribute('data-shading'),
                    color: card2.getAttribute('data-color'),
                };
                const card3Attributes = {
                    number: parseInt(card3.getAttribute('data-number')),
                    symbol: card3.getAttribute('data-symbol'),
                    shading: card3.getAttribute('data-shading'),
                    color: card3.getAttribute('data-color'),
                };

                // Check if the cards form a valid set
                if (isValidSet([card1Attributes, card2Attributes, card3Attributes])) {
                    // Highlight the cards
                    card1.classList.add('highlighted');
                    card2.classList.add('highlighted');
                    card3.classList.add('highlighted');
                    return;
                }
            }
        }
    }

    alert('No valid set found on the board.');
}