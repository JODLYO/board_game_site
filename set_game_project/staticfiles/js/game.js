// set_game/static/set_game/js/game.js

let selectedCards = [];

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
    });
});

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
    } else {
        document.getElementById('message').innerText = 'Invalid set. Try again.';
    }
}

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
