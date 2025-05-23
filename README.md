# File LLM Translation

A program that translates long game files using LLM APIs.

## Main Features

*   Various LLM options (OpenAI, Anthropic, Google Gemini, etc.)
*   API key input
*   Automatic LLM model detection and selection
*   Multiple output language options
*   File input and translated file export

## Note on Testing

*   This program has been primarily tested using the Google Gemini LLM provider.
*   Tested based on Korean translation.

## Installation

1.  Clone the repository
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the program:
    ```bash
    python main.py
    ```

## Usage

1.  Select LLM provider (OpenAI, Anthropic, or Google Gemini)
2.  Enter API key
3.  Select model
4.  Choose output language
5.  Select input file
6.  Click "Start Translation"
7.  Export translated results 
