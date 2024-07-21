let selectedCards = [];
let playerId = null;
let sessionId = null;

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
function sendMove(playerId, cardIds) {
    if (!sessionId) {
        console.error('Session ID is not set.');
        return;
    }
    if (!playerId) {
        console.error('Player ID is not set.');
        return;
    }
    gameSocket.send(JSON.stringify({
        'type': 'make_move',
        'session_id': sessionId,
        'player_id': playerId,
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
        const cardText = cardElement.querySelector('p').innerText.split(' ');
        return {
            number: cardText[0],
            shading: cardText[1],
            color: cardText[2],
            symbol: cardText[3]
        };
    });

    const isValid = isValidSet(cards);
    if (isValid) {
        document.getElementById('message').innerText = 'You found a valid set!';
        console.log('sending move');
        sendMove(playerId, selectedCards);
    } else {
        document.getElementById('message').innerText = 'Invalid set. Try again.';
    }

    // Reset selected cards
    selectedCards.forEach(cardId => {
        const cardElement = document.querySelector(`.card[data-card-id="${cardId}"]`);
        cardElement.classList.remove('selected');
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
        'ws://' + window.location.host + ':8000/ws/game/'
    );

    gameSocket.onopen = function() {
        // Function to send a message to start a new game
        function startGame() {
            gameSocket.send(JSON.stringify({
                'type': 'start_game'
            }));
        }

        // Example usage: Start a new game
        startGame();
    };

    gameSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log('WebSocket message received:', data);

        if (data.type === 'game_state') {
            updateGameState(data.state);
        } else if (data.type === 'game_started') {
            sessionId = data.session_id;  // Store the received session ID
            console.log('Game started with session ID:', sessionId);
            playerId = data.player_ids[0];
            console.log('Player ID set to:', playerId);
        }
    };

    gameSocket.onclose = function(e) {
        console.error('Socket closed unexpectedly');
    };
}

setupWebSocket();

// Function to update the game state
function updateGameState(state) {
    console.log('updateGameState called with state:', state);
    console.trace();

    // Update the board
    const boardContainer = document.getElementById('game-board');
    boardContainer.innerHTML = '';  // Clear current board
    Object.entries(state.board).forEach(([pos, cardId]) => {
        const cardData = state.cards[cardId];
        const cardElement = createCardElement(cardId, cardData);
        cardElement.style.gridArea = `card${pos}`;  // Set the grid area for CSS grid layout
        boardContainer.appendChild(cardElement);
    });

    // Update the scores
    const scoresContainer = document.getElementById('scores');
    scoresContainer.innerHTML = '';  // Clear current scores
    for (const [playerId, score] of Object.entries(state.scores)) {
        const scoreElement = document.createElement('div');
        scoreElement.innerText = `Player ${playerId}: ${score}`;
        scoresContainer.appendChild(scoreElement);
    }

    // Clear the message
    document.getElementById('message').innerText = '';
}


function createCardElement(cardId, cardData) {
    const cardElement = document.createElement('div');
    cardElement.classList.add('card');
    cardElement.setAttribute('data-card-id', cardId);

    const cardText = document.createElement('p');
    cardText.innerText = `${cardData.number} ${cardData.shading} ${cardData.color} ${cardData.symbol}`;
    cardElement.appendChild(cardText);

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
// delete this comment 2