# Checkers Environment for Training RL DQN Agents

This project provides a checkers environment suitable for training RL DQN agents. It comes with a beautiful frontend, which has been implemented from scratch.

## Project Structure

The project repository contains the following files:

- `templates` directory: It includes the Jinja2 templates used for rendering the frontend.
- `app.py`: This file sets up the FastAPI application and defines the routes for handling requests.
- `board.py`: This file contains the implementation of the checkers board, including its initialization, legal moves, and move operations.
- `index.html`: This HTML template represents the main page of the frontend, displaying the checkers board.
- `base.html`: This HTML template serves as the base layout for the frontend, providing a common structure for all pages.

## Installation and Usage

1. Clone the repository to your local machine.
2. Install the required dependencies by running `pip install -r requirements.txt`.
3. Start the application by running `python app.py`.
4. Open your web browser and navigate to `http://localhost:8000` to access the checkers environment.

## Checkers Board Representation

The checkers board is represented as an 8x4 NumPy array. Each dark square on the board represents a piece, while the light squares cannot hold any pieces. The board is drawn visually, but the pieces are not stored in the array. The starting position of the checkers board is provided as a NumPy array named `STARTING_POSITION` in the `board.py` file.

## Board Class

The `Board` class in `board.py` represents the checkers board. It has the following functionalities:

- Initialization: The `Board` class can be initialized with a custom position, which should be an 8x4 NumPy array of `np.int8` data type.
- Legal Moves: The `legal_moves` property returns a list of legal moves for the current player.
- Move Operation: The `move` method allows moving a piece from one square to another.
- Friendly Form: The `friendly_form` property returns a NumPy array representing the board in a friendly format, suitable for display purposes.
- Representation: The `__repr__` method returns a string representation of the checkers board.
- Getter and Setter: The `__getitem__` and `__setitem__` methods provide convenient access to the board positions using square coordinates or `Square` instances.
- Copying: The `__copy__` method allows creating a copy of the board.

## Frontend

The frontend is implemented using HTML and CSS, with the help of the Jinja2 templating engine. The `index.html` template is responsible for rendering the checkers board. It uses a grid-based layout, with each tile representing a square on the checkers board. The tiles are populated dynamically based on the current state of the board.
![image](https://github.com/michalskibinski109/checkers/assets/77834536/7bcf3a5d-4ea1-4124-a2e2-34fcf400ad17)

## Contributing

Contributions to this project are welcome. If you encounter any issues or have suggestions for improvements, please open an issue or submit a pull request on the project repository.

---
