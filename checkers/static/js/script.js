let board = $("#board");
// get `light` css variable
let light = getComputedStyle(document.body).getPropertyValue("--light");
// get `dark` css variable
let dark = getComputedStyle(document.body).getPropertyValue("--dark");

let whitePieceColor = getComputedStyle(document.body).getPropertyValue(
  "--primary"
);
let blackPieceColor = getComputedStyle(document.body).getPropertyValue(
  "--tertiary"
);

// set constants
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

// log constants
console.log("boardPosition", boardPosition.length);
console.log("pseudoLegalKingMoves", pseudoLegalKingMoves);
console.log("pseudoLegalManMoves", pseudoLegalManMoves);
console.log("drawBoard", drawBoard);
console.log("populateBoard", populateBoard);
console.log("showPseudoLegalMoves", showPseudoLegalMoves);
console.log("size", size);

const drawBoardMethod = () => {
  for (let i = 0; i < boardPosition.length; i++) {
    let tile = $(`#tile-${i}`);
    let tileText = $(`#tile-${i}-text`);
    let text = Math.floor(i / 2) + 1;
    if ((i + Math.floor(i / size)) % 2 === 0) {
      tile.css("background-color", light);
      tile.css("color", dark);
      tileText.text(text);
    } else {
      tile.css("background-color", dark);
      tile.css("color", light);
    }
  }
};

const populateBoardMethod = () => {
  let board = $("#board").attr("board");
  let boardArray = JSON.parse(board);
  console.log(boardArray);
  let colorMap = {
    1: whitePieceColor,
    "-1": blackPieceColor,
    10: "#aaa",
    "-10": "#555",
  };
  for (let i = 0; i < boardArray.length; i++) {
    for (let j = 0; j < boardArray[i].length; j++) {
      let tile = $(`#tile-${i * 8 + j}`);
      tile.children(".piece").remove();
      if (boardArray[i][j] !== 0) {
        tile.append(
          `<div class="piece" id="piece-${
            i * 4 + j / 2
          }" style="background-color: ${colorMap[boardArray[i][j]]}"></div>`
        );
      } else {
        // remove piece if it exists but leave text
      }
    }
  }
};

// square click handler
const squareClick = (e) => {
  // get text of square as number
  drawBoard();
  let number = parseInt(e.target.innerText);

  let squares_to_highlight = $("#board").attr("debug");
  squares_to_highlight = JSON.parse(squares_to_highlight);
  list_of_squares = squares_to_highlight[number - 1];
  console.log(list_of_squares);
  list_of_squares.forEach((element) => {
    // get tile with text  attribute == element
    tiles = $(".tile");
    for (let i = 0; i < tiles.length; i++) {
      if (tiles[i].innerText - 1 == element) {
        tiles[i].style.backgroundColor = "red";
      }
    }
  });

  // Uncaught SyntaxError: Expected property name or '}' in JSON at position 1
};
// highlight corresponding squares
//from this dict {0: (5, 11, 16, 22, 27, 33, 38, 44, 49), 1: (6, 12, 17, 23, 28, 34, 39, 45), 2

// make half of the board light and half dark

// on document ready

// on ready
$(document).ready(() => {
  if (drawBoard) drawBoardMethod();

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

function updateBoardPosition(sourceTile, targetTile) {
  let board = $("#board").attr("position");
  let boardArray = JSON.parse(board);

  let sourceIndex = sourceTile.attr("id").split("-")[1];
  let targetIndex = targetTile.attr("id").split("-")[1];

  let piece = boardArray[Math.floor(sourceIndex / 8)][sourceIndex % 8];
  boardArray[Math.floor(sourceIndex / 8)][sourceIndex % 8] = 0;
  boardArray[Math.floor(targetIndex / 8)][targetIndex % 8] = piece;

  $("#board").attr("position", JSON.stringify(boardArray));
}
