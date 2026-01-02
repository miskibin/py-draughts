/**
 * py-draughts - Game Client
 */

// Piece colors
const COLORS = {
    1: '#1a1a1a', '-1': '#f0f0f0',
    2: '#1a1a1a', '-2': '#f0f0f0'
};

// Game state
let board = null;
let history = null;
let turn = null;
let legalMoves = null;
let sourceSquare = null;
let autoPlayId = null;
let autoPlayRunning = false;
let autoPlayNonce = 0;
let autoPlayRequest = null;
let engineMoveInFlight = false;
let playWithComputerMode = false;
let engineDepth = 6;
let lastGameOver = false;

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
                const isWhite = piece > 0;
                $tile.append(`<img src="${crownIcon}" class="crown ${isWhite ? 'crown-light' : ''}" alt="K">`);
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
            const moveNo = m[0];
            const white = m[1] || '';
            const black = m[2] || '';
            const whitePly = (moveNo - 1) * 2 + 1;
            const blackPly = (moveNo - 1) * 2 + 2;

            $list.append(
                `<div class="move-row">
                    <span class="move-number">${moveNo}.</span>
                    <span class="move-white move-cell" data-ply="${whitePly}">${white}</span>
                    <span class="move-black move-cell" data-ply="${blackPly}">${black}</span>
                </div>`
            );
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
        
        // If play with computer mode is enabled and game is not over, let computer play
        if (playWithComputerMode && turn && !data.game_over) {
            await new Promise(resolve => setTimeout(resolve, 500)); // Add delay for UX
            await engineMove();
        }
    }
}

// Button handlers
async function engineMove(opts = { autoplay: false, nonce: 0 }) {
    // Prevent overlapping calls (autoplay depth 10 can exceed interval)
    if (engineMoveInFlight) return;
    engineMoveInFlight = true;

    const $btn = $('#makeMove').prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span>');
    try {
        const req = api.get('/best_move');
        autoPlayRequest = req;
        const data = await req;

        // Ignore autoplay responses if stopped/restarted mid-flight.
        if (opts.autoplay && (!autoPlayRunning || opts.nonce !== autoPlayNonce)) {
            return;
        }

        board = data.position; history = data.history; turn = data.turn;
        updateBoard();

        // Game-over acknowledgement
        if (data.game_over && !lastGameOver) {
            notify('Game Over', `Result: ${data.result || '-'}`, 'info');
        }
        lastGameOver = !!data.game_over;

        if (data.game_over) {
            // Stop autoplay if running
            autoPlayRunning = false;
            if (autoPlayId) {
                clearTimeout(autoPlayId);
                autoPlayId = null;
            }
            $('#autoPlay').html('<i class="bi bi-play-fill"></i> Auto Play');
        }
    } catch {
        notify('Error', 'Engine failed', 'error');
    } finally {
        $btn.prop('disabled', false).html('<i class="bi bi-cpu"></i> Engine Move');
        engineMoveInFlight = false;
    }
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

async function copyPdn() {
    const data = await api.get('/pdn');
    navigator.clipboard.writeText(data.pdn);
    notify('Copied', 'PDN copied to clipboard', 'success');
}

async function loadPdn() {
    const pdn = prompt('Paste PDN:');
    if (!pdn) return;
    try {
        const data = await $.ajax({ url: '/load_pdn', method: 'POST', contentType: 'application/json', data: JSON.stringify({ pdn }) });
        board = data.position; history = data.history; turn = data.turn;
        updateBoard();
        notify('Loaded', 'PDN loaded', 'success');
    } catch { notify('Error', 'Invalid PDN', 'error'); }
}

function toggleAutoPlay() {
    const $btn = $('#autoPlay');
    if (autoPlayRunning) {
        autoPlayRunning = false;
        if (autoPlayId) {
            clearTimeout(autoPlayId);
            autoPlayId = null;
        }
        if (autoPlayRequest && typeof autoPlayRequest.abort === 'function') {
            autoPlayRequest.abort();
        }
        autoPlayRequest = null;
        $btn.html('<i class="bi bi-play-fill"></i> Auto Play');
        return;
    }

    // Start autoplay: chain moves so there is never more than one in-flight request.
    autoPlayRunning = true;
    autoPlayNonce += 1;
    const nonce = autoPlayNonce;
    $btn.html('<i class="bi bi-stop-fill"></i> Stop');

    const tick = async () => {
        if (!autoPlayRunning || nonce !== autoPlayNonce) return;
        await engineMove({ autoplay: true, nonce });
        if (!autoPlayRunning || nonce !== autoPlayNonce) return;
        autoPlayId = setTimeout(tick, 800);
    };

    // Run first move immediately.
    tick();
}

async function gotoPly(ply) {
    const p = parseInt(ply);
    if (!Number.isFinite(p) || p < 0) return;
    const data = await api.get(`/goto/${p}`);
    board = data.position; history = data.history; turn = data.turn;
    updateBoard();
}

async function loadFen() {
    const fen = prompt('Paste FEN:');
    if (!fen) return;
    try {
        const data = await $.ajax({ url: '/load_fen', method: 'POST', contentType: 'application/json', data: JSON.stringify({ fen }) });
        board = data.position; history = data.history; turn = data.turn;
        updateBoard();
        notify('Loaded', 'FEN loaded', 'success');
    } catch { notify('Error', 'Invalid FEN', 'error'); }
}

async function updateEngineDepth(depth) {
    engineDepth = parseInt(depth);
    $('#depthValue').text(engineDepth);
    await api.get(`/set_depth/${engineDepth}`);
    notify('Depth', `Engine depth set to ${engineDepth}`, 'info');
}

async function togglePlayWithComputer() {
    playWithComputerMode = $('#playWithComputerToggle').is(':checked');
    const mode = playWithComputerMode ? 'on' : 'off';
    await api.get(`/set_play_mode/${mode}`);
    $('#computerModeInfo').toggle(playWithComputerMode);
    if (playWithComputerMode) {
        notify('Mode', 'Play with Computer enabled', 'info');
    } else {
        notify('Mode', 'Play with Computer disabled', 'info');
    }
}

// Initialize
$(async () => {
    board = (await api.get('/position')).position;
    initBoard();
    updateBoard();

    // Original button handlers
    $('#makeMove').on('click', engineMove);
    $('#popBtn').on('click', undo);
    $('#randomPos').on('click', randomPosition);
    $('#copyFen').on('click', copyFen);
    $('#copyPdn').on('click', copyPdn);
    $('#loadPdn').on('click', loadPdn);
    $('#autoPlay').on('click', toggleAutoPlay);

    // Clickable move history -> jump to that ply
    $('#moveList').on('click', '.move-cell', function () {
        const ply = $(this).data('ply');
        if (!ply) return;
        gotoPly(ply);
    });

    // New feature handlers
    $('#loadFen').on('click', loadFen);

    $('#depthSlider').on('input', function() {
        updateEngineDepth($(this).val());
    });

    $('#playWithComputerToggle').on('change', togglePlayWithComputer);
});
