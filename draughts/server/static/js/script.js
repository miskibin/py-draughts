/**
 * py-draughts - Game Client
 */

// Piece colors
const COLORS = {
    1: '#f0f0f0', '-1': '#1a1a1a',
    2: '#f0f0f0', '-2': '#1a1a1a'
};

// Game state
let board = null;
let history = null;
let turn = null;
let legalMoves = null;
let sourceSquare = null;
let autoPlayId = null;

const crownIcon = $('#board').data('crown-icon');

// API calls
const api = {
    get: (url) => $.get(url),
    post: (url) => $.post(url)
};

// Show toast notification
function notify(title, message, type = 'success') {
    const icons = { success: 'check-circle-fill text-success', error: 'x-circle-fill text-danger', info: 'info-circle-fill text-info' };
    $('#toastIcon').attr('class', `bi bi-${icons[type]} me-2`);
    $('#toastTitle').text(title);
    $('#toastMessage').text(message);
    new bootstrap.Toast($('#notificationToast')[0]).show();
}

// Update the board display
function updateBoard() {
    const size = Math.sqrt(board.length);
    $('#board').css('grid-template-columns', `repeat(${size}, 1fr)`);
    $('#board').css('grid-template-rows', `repeat(${size}, 1fr)`);

    board.forEach((piece, i) => {
        const $tile = $(`#tile-${i}`);
        $tile.removeClass('highlight').find('.piece, .crown').remove();

        if (piece !== 0) {
            $tile.append(`<div class="piece" style="background:${COLORS[piece]}"></div>`);
            if (Math.abs(piece) > 1) {
                const isBlack = piece < 0;
                $tile.append(`<img src="${crownIcon}" class="crown ${isBlack ? 'crown-light' : ''}" alt="K">`);
            }
        }
    });

    // Update turn
    $('#turn').text(turn || 'White');
    $('#turnIndicator').removeClass('turn-white turn-black').addClass(turn === 'Black' ? 'turn-black' : 'turn-white');

    // Update history
    const $list = $('#moveList').empty();
    if (!history?.length) {
        $list.html('<div class="text-muted text-center py-3">No moves yet</div>');
    } else {
        history.forEach(m => {
            $list.append(`<div class="move-row"><span class="move-number">${m[0]}.</span><span class="move-white">${m[1] || ''}</span><span class="move-black">${m[2] || ''}</span></div>`);
        });
        $list.scrollTop($list[0].scrollHeight);
    }
}

// Initialize board tiles
function initBoard() {
    const size = Math.sqrt(board.length);
    board.forEach((_, i) => {
        const $tile = $(`#tile-${i}`);
        const isLight = (i + Math.floor(i / size)) % 2 !== 0;

        $tile.addClass(isLight ? 'light-tile' : 'dark-tile');
        if (isLight) $(`#tile-${i}-text`).text(Math.floor(i / 2) + 1);

        $tile.on('click', handleTileClick);
    });
}

// Handle clicking a tile
async function handleTileClick(e) {
    const $tile = $(e.currentTarget);
    const $piece = $tile.find('.piece');
    const tileNum = parseInt($tile.find('.tile-text').text());

    // If clicking a piece, show legal moves
    if ($piece.length && !$(e.target).hasClass('tile')) {
        $('.highlight').removeClass('highlight');
        const data = await api.get('/legal_moves');
        legalMoves = JSON.parse(data.legal_moves);

        if (legalMoves[tileNum - 1]) {
            sourceSquare = tileNum;
            legalMoves[tileNum - 1].flat().forEach(target => {
                $('.tile').each(function() {
                    if (parseInt($(this).find('.tile-text').text()) - 1 === target) {
                        $(this).addClass('highlight');
                    }
                });
            });
        }
        return;
    }

    // If clicking highlighted tile, make move
    if (sourceSquare && legalMoves[sourceSquare - 1]?.includes(tileNum - 1)) {
        const data = await api.post(`/move/${sourceSquare}/${tileNum}`);
        board = data.position;
        history = data.history;
        turn = data.turn;
        sourceSquare = null;
        updateBoard();
    }
}

// Button handlers
async function engineMove() {
    const $btn = $('#makeMove').prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span>');
    try {
        const data = await api.get('/best_move');
        board = data.position; history = data.history; turn = data.turn;
        updateBoard();
    } catch { notify('Error', 'Engine failed', 'error'); }
    $btn.prop('disabled', false).html('<i class="bi bi-cpu"></i> Engine Move');
}

async function undo() {
    const data = await api.get('/pop');
    board = data.position; history = data.history; turn = data.turn;
    updateBoard();
    notify('Undo', 'Move undone', 'info');
}

async function randomPosition() {
    const data = await api.get('/set_random_position');
    board = data.position; history = data.history; turn = data.turn;
    updateBoard();
    notify('Random', 'New position set', 'success');
}

async function copyFen() {
    const data = await api.get('/fen');
    navigator.clipboard.writeText(data.fen);
    notify('Copied', data.fen, 'success');
}

function toggleAutoPlay() {
    const $btn = $('#autoPlay');
    if (autoPlayId) {
        clearInterval(autoPlayId);
        autoPlayId = null;
        $btn.html('<i class="bi bi-play-fill"></i> Auto Play');
    } else {
        autoPlayId = setInterval(engineMove, 800);
        $btn.html('<i class="bi bi-stop-fill"></i> Stop');
    }
}

// Initialize
$(async () => {
    board = (await api.get('/position')).position;
    initBoard();
    updateBoard();

    $('#makeMove').on('click', engineMove);
    $('#popBtn').on('click', undo);
    $('#randomPos').on('click', randomPosition);
    $('#copyFen').on('click', copyFen);
    $('#autoPlay').on('click', toggleAutoPlay);
});
