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

const populateBoard = () => {
  let board = $("#board").attr("position");
  let boardArray = JSON.parse(board);
  console.log(boardArray);
  let colorMap = {
    1: whitePieceColor,
    "-1": blackPieceColor,
  };
  for (let i = 0; i < boardArray.length; i++) {
    for (let j = 0; j < boardArray[i].length; j++) {
      let tile = $(`#tile-${i * 8 + j}`);
      if (boardArray[i][j] !== 0) {
        tile.append(
          `<div class="piece" id="piece-${
            i * 4 + j / 2
          }" style="background-color: ${colorMap[boardArray[i][j]]}"></div>`
        );
      }
    }
  }
};

// make half of the board light and half dark
const drawBoard = () => {
  let cols = ["A", "B", "C", "D", "E", "F", "G", "H"];
  let rows = ["1", "2", "3", "4", "5", "6", "7", "8"];
  for (let i = 0; i < 64; i++) {
    let tile = $(`#tile-${i}`);
    let tileText = $(`#tile-${i}-text`);
    let text = cols[i % 8] + rows[Math.floor(i / 8)];
    tileText.text(text);
    if ((i + Math.floor(i / 8)) % 2 === 0) {
      tile.css("background-color", light);
      tile.css("color", dark);
    } else {
      tile.css("background-color", dark);
      tile.css("color", light);
    }
  }
};

// on ready
$(document).ready(() => {
  drawBoard();
  populateBoard();
  // all pieces should have position: absolute

  dragPiece();
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
