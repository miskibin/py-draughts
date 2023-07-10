let board = $("#board");
// get `light` css variable
let light = getComputedStyle(document.body).getPropertyValue("--light");
// get `dark` css variable
let dark = getComputedStyle(document.body).getPropertyValue("--dark");

let whiteManColor = getComputedStyle(document.body).getPropertyValue(
  "--white-man"
);
let blackManColor = getComputedStyle(document.body).getPropertyValue(
  "--black-man"
);
let blackKingColor = getComputedStyle(document.body).getPropertyValue(
  "--black-king"
);
let whiteKingColor = getComputedStyle(document.body).getPropertyValue(
  "--white-king"
);

let redColor = getComputedStyle(document.body).getPropertyValue("--red");

const colorMap = {
  1: whiteManColor,
  "-1": blackManColor,
  10: whiteManColor,
  "-10": blackManColor,
};

// ######################### constants #########################
var boardArray = JSON.parse($("#board").attr("board"));
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
const size = Math.floor(Math.sqrt(boardArray.length));

const crown_icon = $("#board").attr("crown_icon");
// ######################### constants #########################

const drawBoardMethod = () => {
  for (let i = 0; i < boardArray.length; i++) {
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
  for (let i = 0; i < boardArray.length; i++) {
    let tile = $(`#tile-${i}`);
    tile.children(".piece").remove();
    console.log(tile.attr("tile-number"));
    if (boardArray[i] !== 0) {
      tile.append(
        `<div class="piece" id="piece-${i}" style="background-color: ${
          colorMap[boardArray[i]]
        }"></div>`
      );
      if (Math.abs(boardArray[i]) > 1) {
        $(`#tile-${i}`).append(`<img src="${crown_icon}" class="crown" />`);
      }
    }
  }
};
// square click handler

const showPseudoLegalMovesMethod = (square, king = false) => {
  drawBoardMethod();
  //  get tile number from attr
  console.log(square);
  if (king) {
    squares_to_highlight = pseudoLegalKingMoves[square - 1];
  } else {
    squares_to_highlight = pseudoLegalManMoves[square - 1];
  }
  squares_to_highlight.flat().forEach((element) => {
    tiles = $(".tile");
    for (let i = 0; i < tiles.length; i++) {
      if (tiles[i].innerText - 1 == element) {
        tiles[i].style.backgroundColor = redColor;
      }
    }
  });
};

const showPseudoLegalMovesForPieceMethod = (e) => {
  let number = $(e.target).parent().attr("tile-number");
  let pieceValue = boardArray[number];
  let square = parseInt($(e.target).parent().text());
  showPseudoLegalMovesMethod(square, Math.abs(pieceValue) > 2);
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
