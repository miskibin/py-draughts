let light = getComputedStyle(document.body).getPropertyValue("--light");

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
var boardArray = null;
var legalMoves = null;
var size = null;
const crown_icon = $("#board").attr("crown_icon");
// ######################### constants #########################

// ####################### REQUESTS ############################
const getLegalMoves = () =>
  new Promise((resolve, reject) =>
    $.ajax({
      url: "/legal_moves",
      type: "GET",
      success: (data) => resolve(JSON.parse(data["legal_moves"])),
      error: reject,
    })
  );

const getPosition = () =>
  new Promise((resolve, reject) =>
    $.ajax({
      url: "position",
      type: "GET",
      success: (data) => resolve(data["position"]),
      error: reject,
    })
  );

const makeBestMove = () => {
  $.ajax({
    url: "best_move",
    type: "GET",
    success: (data) => {
      boardArray = data["position"];
      upadateBoard();
    },
  });
};

const pop = () => {
  $.ajax({
    url: "pop",
    type: "GET",
    success: (data) => {
      boardArray = data["position"];
      upadateBoard();
    },
  });
};

// ####################### REQUESTS ############################

const showLegalMoves = async (e) => {
  let square = parseInt($(e.target).parent().text());
  $(".higlight").removeClass("higlight");
  let legalMoves = await getLegalMoves();
  if (!(square - 1 in legalMoves)) return;
  let squaresToHighlight = legalMoves[square - 1].flat();
  squaresToHighlight.forEach((element) => {
    tiles = $(".tile");
    for (let i = 0; i < tiles.length; i++) {
      if (tiles[i].innerText - 1 == element) {
        $(tiles[i]).addClass("higlight");
      }
    }
  });
};

// ############### MANIPULATING DOM ############################

const upadateBoard = () => {
  for (let i = 0; i < boardArray.length; i++) {
    let tile = $(`#tile-${i}`);
    $(".higlight").removeClass("higlight");
    tile.children(".piece").remove();
    tile.children(".crown").remove();
    if (boardArray[i] !== 0) {
      tile.append(
        `<div class="piece" id="piece-${i}" style="background-color: ${
          colorMap[boardArray[i]]
        }"></div>`
      );
      $(`#piece-${i}`).click(showLegalMoves);
      if (Math.abs(boardArray[i]) > 1) {
        $(`#tile-${i}`).append(`<img src="${crown_icon}" class="crown" />`);
      }
    }
  }
};

const init = (boardArray) => {
  size = Math.floor(Math.sqrt(boardArray.length));
  $("#board").css("grid-template-columns", `repeat(${size}, 1fr)`);
  $("#board").css("grid-template-rows", `repeat(${size}, 1fr)`);
  for (let i = 0; i < boardArray.length; i++) {
    let tile = $(`#tile-${i}`);
    let tileText = $(`#tile-${i}-text`);
    let text = Math.floor(i / 2) + 1;
    if ((i + Math.floor(i / size)) % 2 === 0) {
      tile.addClass("dark-tile");
    } else {
      tileText.text(text);
      tile.addClass("light-tile");
    }
  }
};
// ############### MANIPULATING DOM ############################

// on ready
$(document).ready(async () => {
  boardArray = await getPosition();
  init(boardArray);
  upadateBoard();
  $("#makeMove").click(makeBestMove);
  $("#popBtn").click(pop);
});
