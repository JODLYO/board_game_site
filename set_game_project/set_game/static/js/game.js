// Add rematch request button to the game UI
function addRematchButton() {
    const rematchButton = document.createElement('button');
    rematchButton.id = 'rematch-button';
    rematchButton.className = 'btn btn-primary';
    rematchButton.textContent = 'Request Rematch';
    rematchButton.onclick = requestRematch;
    document.getElementById('game-controls').appendChild(rematchButton);
}

// Request a rematch
function requestRematch() {
    const rematchButton = document.getElementById('rematch-button');
    rematchButton.disabled = true;
    rematchButton.textContent = 'Rematch Requested';

    // Send rematch request to the server
    gameSocket.send(JSON.stringify({
        'type': 'request_rematch'
    }));
}

// Handle rematch request from another player
function handleRematchRequested(data) {
    const playerName = data.player_name;
    showNotification(`${playerName} has requested a rematch!`);
}

// Handle rematch started
function handleRematchStarted(data) {
    // Reset the game UI
    resetGameUI();

    // Update the game state with the new game
    updateGameState(data.game_state);

    // Enable the rematch button
    const rematchButton = document.getElementById('rematch-button');
    rematchButton.disabled = false;
    rematchButton.textContent = 'Request Rematch';

    showNotification('Rematch started!');
}

// Reset the game UI
function resetGameUI() {
    // Clear the board
    const board = document.getElementById('game-board');
    board.innerHTML = '';

    // Reset scores
    document.getElementById('player1-score').textContent = '0';
    document.getElementById('player2-score').textContent = '0';

    // Clear any notifications
    clearNotifications();
}

// Update the game state
function updateGameState(gameState) {
    // Update the board
    const board = document.getElementById('game-board');
    board.innerHTML = '';

    // Create cards for the new game state
    gameState.cards.forEach(card => {
        const cardElement = createCardElement(card);
        board.appendChild(cardElement);
    });

    // Update scores
    document.getElementById('player1-score').textContent = gameState.player1_score;
    document.getElementById('player2-score').textContent = gameState.player2_score;
}

// Add event listeners for rematch messages
gameSocket.addEventListener('message', function (event) {
    const data = JSON.parse(event.data);

    if (data.type === 'rematch_requested') {
        handleRematchRequested(data);
    } else if (data.type === 'rematch_started') {
        handleRematchStarted(data);
    }
    // ... existing code ...
});

// Add rematch button when the game starts
document.addEventListener('DOMContentLoaded', function () {
    // ... existing code ...
    addRematchButton();
});

// Rematch functionality
function handleRematch() {
    const rematchButton = document.getElementById('rematch-button');
    rematchButton.disabled = true;

    fetch('/game/rematch/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Rematch request sent! Waiting for opponent...');
                // Poll for rematch status
                pollRematchStatus();
            } else {
                showNotification('Failed to send rematch request. Please try again.');
                rematchButton.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('An error occurred. Please try again.');
            rematchButton.disabled = false;
        });
}

function pollRematchStatus() {
    const pollInterval = setInterval(() => {
        fetch('/game/rematch-status/')
            .then(response => response.json())
            .then(data => {
                if (data.rematch_accepted) {
                    clearInterval(pollInterval);
                    showNotification('Rematch accepted! Starting new game...');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                }
            })
            .catch(error => {
                console.error('Error polling rematch status:', error);
                clearInterval(pollInterval);
            });
    }, 2000); // Poll every 2 seconds
}

// Notification system
function showNotification(message) {
    const notificationsContainer = document.getElementById('notifications');
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;

    notificationsContainer.appendChild(notification);

    // Remove notification after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            notificationsContainer.removeChild(notification);
        }, 300);
    }, 5000);
}

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
} 