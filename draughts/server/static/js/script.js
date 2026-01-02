/**
 * py-draughts - Game Client
 * Clean, modular implementation with dual engine support
 */

// =============================================================================
// Constants & State
// =============================================================================

const COLORS = {
    1: '#1a1a1a', '-1': '#f0f0f0',
    2: '#1a1a1a', '-2': '#f0f0f0'
};

const state = {
    board: null,
    history: null,
    turn: null,
    legalMoves: null,
    sourceSquare: null,
    autoPlayId: null,
    autoPlayRunning: false,
    autoPlayNonce: 0,
    autoPlayRequest: null,
    engineMoveInFlight: false,
    engineDepth: 6,
    lastGameOver: false,
    hasDualEngines: false,
    whiteEngineName: null,
    blackEngineName: null
};

const crownIcon = $('#board').data('crown-icon');

// =============================================================================
// API
// =============================================================================

const api = {
    get: (url) => $.get(url),
    post: (url, data) => data 
        ? $.ajax({ url, method: 'POST', contentType: 'application/json', data: JSON.stringify(data) })
        : $.post(url)
};

// =============================================================================
// Notifications
// =============================================================================

function notify(title, message, type = 'success') {
    const icons = {
        success: 'check-circle-fill text-success',
        error: 'x-circle-fill text-danger',
        info: 'info-circle-fill text-info'
    };
    $('#toastIcon').attr('class', `bi bi-${icons[type]} me-2`);
    $('#toastTitle').text(title);
    $('#toastMessage').text(message);
    new bootstrap.Toast($('#notificationToast')[0]).show();
}

// =============================================================================
// Board Rendering
// =============================================================================

function updateBoard() {
    const size = Math.sqrt(state.board.length);
    $('#board').css({
        'grid-template-columns': `repeat(${size}, 1fr)`,
        'grid-template-rows': `repeat(${size}, 1fr)`
    });

    state.board.forEach((piece, i) => {
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

    updateTurnIndicator();
    updateMoveHistory();
    updateEngineIndicator();
}

function updateTurnIndicator() {
    const turn = state.turn || 'White';
    const capitalizedTurn = turn.charAt(0).toUpperCase() + turn.slice(1);
    $('#turn').text(capitalizedTurn);
    $('#turnIndicator')
        .removeClass('turn-white turn-black')
        .addClass(turn.toLowerCase() === 'black' ? 'turn-black' : 'turn-white');
}

function updateMoveHistory() {
    const $list = $('#moveList').empty();
    
    if (!state.history?.length) {
        $list.html('<div class="text-muted text-center py-3">No moves yet</div>');
        return;
    }

    state.history.forEach(m => {
        const moveNo = m[0];
        const white = m[1] || '';
        const black = m[2] || '';
        const whitePly = (moveNo - 1) * 2 + 1;
        const blackPly = (moveNo - 1) * 2 + 2;

        $list.append(`
            <div class="move-row">
                <span class="move-number">${moveNo}.</span>
                <span class="move-white move-cell" data-ply="${whitePly}">${white}</span>
                <span class="move-black move-cell" data-ply="${blackPly}">${black}</span>
            </div>
        `);
    });
    
    $list.scrollTop($list[0].scrollHeight);
}

function updateEngineIndicator() {
    const $indicator = $('#engineIndicator');
    
    if (!state.hasDualEngines) {
        $indicator.hide();
        return;
    }

    const currentEngine = state.turn === 'white' 
        ? state.whiteEngineName 
        : state.blackEngineName;
    
    $indicator.show();
    $('#currentEngineName').text(currentEngine || 'Engine');
}

function initBoard() {
    const size = Math.sqrt(state.board.length);
    
    state.board.forEach((_, i) => {
        const $tile = $(`#tile-${i}`);
        const isLight = (i + Math.floor(i / size)) % 2 !== 0;

        $tile.addClass(isLight ? 'light-tile' : 'dark-tile');
        if (isLight) {
            $(`#tile-${i}-text`).text(Math.floor(i / 2) + 1);
        }
        $tile.on('click', handleTileClick);
    });
}

// =============================================================================
// User Interaction
// =============================================================================

async function handleTileClick(e) {
    const $tile = $(e.currentTarget);
    const $piece = $tile.find('.piece');
    const tileNum = parseInt($tile.find('.tile-text').text());

    // Clicking a piece: show legal moves
    if ($piece.length && !$(e.target).hasClass('tile')) {
        $('.highlight').removeClass('highlight');
        const data = await api.get('/legal_moves');
        state.legalMoves = JSON.parse(data.legal_moves);

        if (state.legalMoves[tileNum - 1]) {
            state.sourceSquare = tileNum;
            state.legalMoves[tileNum - 1].flat().forEach(target => {
                $('.tile').each(function() {
                    if (parseInt($(this).find('.tile-text').text()) - 1 === target) {
                        $(this).addClass('highlight');
                    }
                });
            });
        }
        return;
    }

    // Clicking highlighted tile: make move
    if (state.sourceSquare && state.legalMoves[state.sourceSquare - 1]?.includes(tileNum - 1)) {
        const data = await api.post(`/move/${state.sourceSquare}/${tileNum}`);
        updateState(data);
        state.sourceSquare = null;
        updateBoard();
    }
}

// =============================================================================
// Game Actions
// =============================================================================

async function engineMove(opts = { autoplay: false, nonce: 0 }) {
    if (state.engineMoveInFlight) return;
    state.engineMoveInFlight = true;

    const $btn = $('#makeMove')
        .prop('disabled', true)
        .html('<span class="spinner-border spinner-border-sm"></span>');

    try {
        const req = api.get('/best_move');
        state.autoPlayRequest = req;
        const data = await req;

        // Ignore stale autoplay responses
        if (opts.autoplay && (!state.autoPlayRunning || opts.nonce !== state.autoPlayNonce)) {
            return;
        }

        updateState(data);
        updateBoard();

        // Game over handling
        if (data.game_over && !state.lastGameOver) {
            notify('Game Over', `Result: ${data.result || '-'}`, 'info');
            stopAutoPlay();
        }
        state.lastGameOver = !!data.game_over;

    } catch (err) {
        if (err.statusText !== 'abort') {
            notify('Error', 'Engine failed', 'error');
        }
    } finally {
        $btn.prop('disabled', false).html('<i class="bi bi-cpu"></i> Engine Move');
        state.engineMoveInFlight = false;
    }
}

async function undo() {
    const data = await api.get('/pop');
    updateState(data);
    updateBoard();
    notify('Undo', 'Move undone', 'info');
}

async function gotoPly(ply) {
    const p = parseInt(ply);
    if (!Number.isFinite(p) || p < 0) return;
    
    const data = await api.get(`/goto/${p}`);
    updateState(data);
    updateBoard();
}

// =============================================================================
// Auto Play
// =============================================================================

function toggleAutoPlay() {
    if (state.autoPlayRunning) {
        stopAutoPlay();
    } else {
        startAutoPlay();
    }
}

function startAutoPlay() {
    state.autoPlayRunning = true;
    state.autoPlayNonce += 1;
    const nonce = state.autoPlayNonce;
    
    $('#autoPlay').html('<i class="bi bi-stop-fill"></i> Stop');

    const tick = async () => {
        if (!state.autoPlayRunning || nonce !== state.autoPlayNonce) return;
        await engineMove({ autoplay: true, nonce });
        if (!state.autoPlayRunning || nonce !== state.autoPlayNonce) return;
        state.autoPlayId = setTimeout(tick, 800);
    };

    tick();
}

function stopAutoPlay() {
    state.autoPlayRunning = false;
    
    if (state.autoPlayId) {
        clearTimeout(state.autoPlayId);
        state.autoPlayId = null;
    }
    
    if (state.autoPlayRequest?.abort) {
        state.autoPlayRequest.abort();
    }
    state.autoPlayRequest = null;
    
    $('#autoPlay').html('<i class="bi bi-play-fill"></i> Auto Play');
}

// =============================================================================
// FEN/PDN Operations
// =============================================================================

async function copyFen() {
    const data = await api.get('/fen');
    await navigator.clipboard.writeText(data.fen);
    notify('Copied', data.fen, 'success');
}

async function copyPdn() {
    const data = await api.get('/pdn');
    await navigator.clipboard.writeText(data.pdn);
    notify('Copied', 'PDN copied to clipboard', 'success');
}

async function loadFen() {
    const fen = prompt('Paste FEN:');
    if (!fen) return;
    
    try {
        const data = await api.post('/load_fen', { fen });
        updateState(data);
        updateBoard();
        notify('Loaded', 'FEN loaded', 'success');
    } catch {
        notify('Error', 'Invalid FEN', 'error');
    }
}

async function loadPdn() {
    const pdn = prompt('Paste PDN:');
    if (!pdn) return;
    
    try {
        const data = await api.post('/load_pdn', { pdn });
        updateState(data);
        updateBoard();
        notify('Loaded', 'PDN loaded', 'success');
    } catch {
        notify('Error', 'Invalid PDN', 'error');
    }
}

// =============================================================================
// Settings
// =============================================================================

async function updateEngineDepth(depth) {
    state.engineDepth = parseInt(depth);
    $('#depthValue').text(state.engineDepth);
    await api.get(`/set_depth/${state.engineDepth}`);
    notify('Depth', `Engine depth set to ${state.engineDepth}`, 'info');
}

// =============================================================================
// Engine Info
// =============================================================================

async function loadEngineInfo() {
    try {
        const info = await api.get('/engine_info');
        state.hasDualEngines = !!(info.white_engine && info.black_engine);
        state.whiteEngineName = info.white_engine;
        state.blackEngineName = info.black_engine;
        state.engineDepth = info.depth;
        
        $('#depthSlider').val(info.depth);
        $('#depthValue').text(info.depth);
        
        updateEngineDisplay();
    } catch {
        // Engine info not available
    }
}

function updateEngineDisplay() {
    if (state.hasDualEngines) {
        $('#engineMatchInfo').show();
        $('#whiteEngineName').text(state.whiteEngineName);
        $('#blackEngineName').text(state.blackEngineName);
    } else {
        $('#engineMatchInfo').hide();
    }
}

// =============================================================================
// Utilities
// =============================================================================

function updateState(data) {
    state.board = data.position;
    state.history = data.history;
    state.turn = data.turn;
}

// =============================================================================
// Initialization
// =============================================================================

$(async () => {
    // Load initial state
    const positionData = await api.get('/position');
    state.board = positionData.position;
    state.history = positionData.history;
    state.turn = positionData.turn;
    
    await loadEngineInfo();
    
    initBoard();
    updateBoard();

    // Button handlers
    $('#makeMove').on('click', () => engineMove());
    $('#popBtn').on('click', undo);
    $('#copyFen').on('click', copyFen);
    $('#copyPdn').on('click', copyPdn);
    $('#loadFen').on('click', loadFen);
    $('#loadPdn').on('click', loadPdn);
    $('#autoPlay').on('click', toggleAutoPlay);

    // Move history navigation
    $('#moveList').on('click', '.move-cell', function() {
        const ply = $(this).data('ply');
        if (ply) gotoPly(ply);
    });

    // Depth slider
    $('#depthSlider').on('input', function() {
        updateEngineDepth($(this).val());
    });
});
