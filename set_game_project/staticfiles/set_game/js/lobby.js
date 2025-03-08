function updateLobbyStatus(data) {
    console.log('updateLobbyStatus called with data:', data);
    const playersDiv = document.getElementById('players');
    playersDiv.innerHTML = '';
    data.players.forEach(player => {
        const playerElement = document.createElement('div');
        playerElement.innerText = `${player.username} ${player.ready ? '✅ Ready' : '❌ Not Ready'}`;
        playersDiv.appendChild(playerElement);
    });

    const waitingMessageDiv = document.getElementById('waiting-message');
    const readyButtonDiv = document.getElementById('ready-button');

    if (data.players.length === 1) {
        // Show waiting message if there's only one player
        waitingMessageDiv.style.display = 'block';
        readyButtonDiv.innerHTML = ''; // Hide the ready button
    } else {
        // Hide waiting message if there are two players
        waitingMessageDiv.style.display = 'none';

        if (data.is_full && !data.all_ready) {
            // Show the ready button if the lobby is full but not all players are ready
            readyButtonDiv.innerHTML = `
                <form id="ready-form" method="post">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${data.csrf_token}">
                    <button type="submit">I'm Ready</button>
                </form>
            `;

            // Add an event listener to the form to prevent default submission
            const readyForm = document.getElementById('ready-form');
            readyForm.addEventListener('submit', function (event) {
                event.preventDefault(); // Prevent the default form submission

                // Send a POST request using fetch
                fetch('/lobby/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': data.csrf_token
                    },
                    body: new URLSearchParams(new FormData(readyForm))
                })
                    .then(response => response.json())
                    .then(data => {
                        console.log(data); // For debugging purposes
                        updateLobbyStatus(data);
                    })
                    .catch(error => console.error('Error submitting ready status:', error));
            });

        } else {
            readyButtonDiv.innerHTML = ''; // Hide the ready button
        }
    }

    if (data.is_full && data.all_ready && data.game_state_id) {
        // Redirect to the game board when both players are ready
        window.location.href = `/game/${data.game_state_id}/`;
    }
}

// Get the lobby ID from the data attribute
const lobbyId = document.getElementById('lobby-id').getAttribute('data-lobby-id');

setInterval(() => {
    fetch(`/api/lobby_status/${lobbyId}/`)
        .then(response => response.json())
        .then(data => {
            console.log(data); // For debugging purposes
            if (data.game_state_id) {
                // Redirect to the game board
                window.location.href = `/game/${data.game_state_id}/`;
            } else {
                // Update the lobby status
                updateLobbyStatus(data);
            }
        })
        .catch(error => console.error('Error fetching lobby status:', error));
}, 3000);