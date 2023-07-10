let board = $("#board");
// get `light` css variable
let light = getComputedStyle(document.body).getPropertyValue("--light");
// get `dark` css variable
let dark = getComputedStyle(document.body).getPropertyValue("--dark");

let whiteManColor = getComputedStyle(document.body).getPropertyValue(
  "--primary"
);
let blackManColor = getComputedStyle(document.body).getPropertyValue(
  "--tertiary"
);
let blackKingColor = getComputedStyle(document.body).getPropertyValue(
  "--black-king"
);
let whiteKingColor = getComputedStyle(document.body).getPropertyValue(
  "--white-king"
);

let ceruleanColor = getComputedStyle(document.body).getPropertyValue(
  "--cerulean"
);

const colorMap = {
  1: whiteManColor,
  "-1": blackManColor,
  10: whiteKingColor,
  "-10": blackKingColor,
};

// ######################### constants #########################
var boardPosition = JSON.parse($("#board").attr("board"));
const pseudoLegalKingMoves = JSON.parse(
  $("#board").attr("pseudo_legal_king_moves")
);
const pseudoLegalManMoves = JSON.parse(
  $("#board").attr("pseudo_legal_man_moves")
);
const drawBoard = JSON.parse($("#board").attr("draw_board"));
const populateBoard = JSON.parse($("#board").attr("populate_board"));
const showPseudoLegalMoves = JSON.parse(
  $("#board").attr("show_pseudo_legal_moves")
);
const size = Math.floor(Math.sqrt(boardPosition.length));
// ######################### constants #########################

const drawBoardMethod = () => {
  for (let i = 0; i < boardPosition.length; i++) {
    let tile = $(`#tile-${i}`);
    let tileText = $(`#tile-${i}-text`);
    let text = Math.floor(i / 2) + 1;
    if ((i + Math.floor(i / size)) % 2 === 0) {
      tile.css("color", light);
      tile.css("background-color", dark);
    } else {
      tileText.text(text);
      tile.css("background-color", light);
      tile.css("color", dark);
    }
  }
};

const populateBoardMethod = () => {
  for (let i = 0; i < boardPosition.length; i++) {
    let tile = $(`#tile-${i}`);
    tile.children(".piece").remove();
    console.log(tile.attr("tile-number"));
    if (boardPosition[i] !== 0) {
      tile.append(
        `<div class="piece" id="piece-${i}" style="background-color: ${
          colorMap[boardPosition[i]]
        }"></div>`
      );
    }
  }
};
// square click handler

const showPseudoLegalMovesMethod = (square, king = false) => {
  drawBoardMethod();
  //  get tile number from attr
  console.log(square);
  let squares_to_highlight = pseudoLegalKingMoves[square - 1];
  if (king) {
    squares_to_highlight = pseudoLegalKingMoves[square - 1];
  } else {
    squares_to_highlight = pseudoLegalManMoves[square - 1];
  }
  console.log(squares_to_highlight.flat());
  squares_to_highlight.flat().forEach((element) => {
    tiles = $(".tile");
    for (let i = 0; i < tiles.length; i++) {
      if (tiles[i].innerText - 1 == element) {
        tiles[i].style.backgroundColor = ceruleanColor;
      }
    }
  });
};

const showPseudoLegalMovesForPieceMethod = (e) => {
  let number = $(e.target).parent().attr("tile-number");
  let pieceValue = boardPosition[number];
  let square = parseInt($(e.target).parent().text());
  console.log(number, pieceValue, square);
  if (Math.abs(pieceValue) < 2) {
    showPseudoLegalMovesMethod(square, false);
  } else {
    showPseudoLegalMovesMethod(square, true);
  }
};

const init = () => {
  // set attr     style="grid-template-columns: {{size}}; grid-template-rows: {{size}};"
  $("#board").css("grid-template-columns", `repeat(${size}, 1fr)`);
  $("#board").css("grid-template-rows", `repeat(${size}, 1fr)`);
};
// on ready
$(document).ready(() => {
  init();
  if (drawBoard) drawBoardMethod();
  if (populateBoard) populateBoardMethod();
  if (showPseudoLegalMoves) {
    // $(".tile").click((e) => {
    //   showPseudoLegalMovesMethod(parseInt($(e.target).text()), true);
    // });
    $(".piece").click((e) => {
      showPseudoLegalMovesForPieceMethod(e);
    });
  }
  // add click handler to squares
  // $(".tile").click(squareClick);

  // populateBoard();

  // // call /random_move and /board in a loop
  // setInterval(() => {
  //   $.ajax({
  //     url: "/random_move",
  //     type: "GET",
  //     success: (data) => {
  //       console.log(data);
  //       $("#board").attr("position", JSON.stringify(data["position"]));
  //       populateBoard();
  //     },
  //   });
  // }, 900);

  // dragPiece();
});
function dragPiece() {
  $(".piece").draggable({
    containment: "#board",
    cursor: "move",
    revert: true,
    stack: ".piece",
    start: function (event, ui) {
      //  position: absolute;
      console.log("start");
      $(this).css("position", "absolute");
    },
  });

  $(".tile").droppable({
    accept: ".piece",
    drop: function (event, ui) {
      let targetTile = $(this);

      // Check if the target tile already has a piece
      if (targetTile.children(".piece").length > 0) {
        return; // Prevent placing a piece on another piece
      }

      let piece = ui.draggable;
      let sourceTile = piece.parent();

      // Move the piece to the target tile
      piece.css({ top: 0, left: 0, position: "static" });
      // piece.css({ top: "", left: "", position: "static" });
      targetTile.append(piece);
      //disable piece position: absolute

      // Update the position attribute of the board
      updateBoardPosition(sourceTile, targetTile);
    },
  });
}

// function updateBoardPosition(sourceTile, targetTile) {
//   let board = $("#board").attr("position");
//   let boardArray = JSON.parse(board);

//   let sourceIndex = sourceTile.attr("id").split("-")[1];
//   let targetIndex = targetTile.attr("id").split("-")[1];

//   let piece = boardArray[Math.floor(sourceIndex / 8)][sourceIndex % 8];
//   boardArray[Math.floor(sourceIndex / 8)][sourceIndex % 8] = 0;
//   boardArray[Math.floor(targetIndex / 8)][targetIndex % 8] = piece;

//   $("#board").attr("position", JSON.stringify(boardArray));
// }
