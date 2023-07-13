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
  2: whiteManColor,
  "-2": blackManColor,
};

// ######################### constants #########################
var boardArray = null;
var legalMoves = null;
var historyData = null;
var turn = null;
var size = null;
const crown_icon = $("#board").attr("crown_icon");
var sourceSquare = null;
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
const postMove = (source, target) =>
  $.ajax({
    url: `move/${source}/${target}`,
    type: "POST",
    success: (data) => {
      boardArray = data["position"];
      historyData = data["history"];
      turn = data["turn"];
      upadateBoard();
    },
  });

const getFen = () =>
  $.ajax({
    url: "fen",
    type: "GET",
    success: (data) => {
      navigator.clipboard.writeText(data["fen"]);
      alert("Copied the text: " + data["fen"]);
    },
  });

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
      historyData = data["history"];
      turn = data["turn"];
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
      historyData = data["history"];
      turn = data["turn"];
      upadateBoard();
    },
  });
};
const getRandomPos = () => {
  $.ajax({
    url: "set_random_position",
    type: "GET",
    success: (data) => {
      boardArray = data["position"];
      historyData = data["history"];
      turn = data["turn"];
      upadateBoard();
    },
  });
};

// ####################### REQUESTS ############################

// ############### MANIPULATING DOM ############################

const handleSquareClick = (e) => {
  if (!sourceSquare) {
    sourceSquare = null;
    return;
  }
  let targetSquare = parseInt($(e.target).text());
  console.log(sourceSquare, targetSquare);
  console.log(legalMoves);
  if (
    sourceSquare - 1 in legalMoves &&
    legalMoves[sourceSquare - 1].includes(targetSquare - 1)
  ) {
    postMove(sourceSquare, targetSquare);
    sourceSquare = null;
  }
};

const showLegalMoves = async (e) => {
  let square = parseInt($(e.target).parent().text());
  $(".higlight").removeClass("higlight");
  legalMoves = await getLegalMoves();
  if (!(square - 1 in legalMoves)) return;
  sourceSquare = square; // for handling move
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

const updatehistory = () => {
  let tbody = $("#historyTableBody");
  tbody.empty();
  if (!historyData) return;
  for (let i = 0; i < historyData.length; i++) {
    if (!historyData[i][2]) historyData[i][2] = "-";
    tbody.append(
      `<tr><td>${historyData[i][0]}</td><td>${historyData[i][1]}</td><td>${historyData[i][2]}</td></tr>`
    );
  }
  $("#historyContainer").scrollTop($("#historyContainer")[0].scrollHeight);
};

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
        $(`#tile-${i}`).append(
          `<img src="${crown_icon}" alt="crown" class="crown" />`
        );
      }
    }
  }
  updatehistory();
  $("#turn").text(turn);
};

const init = (boardArray) => {
  size = Math.floor(Math.sqrt(boardArray.length));
  $("#board").css("grid-template-columns", `repeat(${size}, 1fr)`);
  $("#board").css("grid-template-rows", `repeat(${size}, 1fr)`);
  for (let i = 0; i < boardArray.length; i++) {
    let tile = $(`#tile-${i}`);
    tile.click(handleSquareClick);
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
  $("#randomPos").click(getRandomPos);
  $("#copyFen").click(getFen);
});
