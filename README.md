# AI Weather Agent with MCP, Gemini and Playwright

## Overview

This project implements an AI Agent that retrieves current weather information for cities in Israel using the Model Context Protocol (MCP), Google Gemini, and Playwright.

When the user asks for the weather in a city, the agent opens a weather website, searches for the requested city, extracts the weather information from the page, and returns an answer based on the website's content.

The project also includes a simple retrieval step, where the weather information is extracted from the web page and provided to the language model as additional context before generating the final response.

---

## Technologies

- Python
- Google Gemini API
- MCP (Model Context Protocol)
- Playwright
- AsyncIO
- python-dotenv

---

## Project Structure

```
host.py                 # Main chat application
client.py               # MCP client
weather_Israel.py       # MCP weather server
README.md
requirements.txt
```

---

## How It Works

1. The user asks for the weather in an Israeli city.
2. Gemini selects the appropriate MCP tools.
3. Playwright opens the weather website.
4. The requested city is entered into the search box.
5. The city is selected from the autocomplete list.
6. The weather page is loaded.
7. The weather information is extracted from the page.
8. The extracted text is returned to Gemini.
9. Gemini generates the final answer using the extracted information.

---

## Features

- Supports weather queries for cities in Israel.
- Accepts city names in Hebrew or English.
- Uses Playwright to navigate a live weather website.
- Extracts weather information directly from the website.
- Provides the extracted content to the language model before answering.
- Uses the website content instead of relying on the model's internal knowledge.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/YisNiz/AI-MCP-with-RAG-project
```

Install the required packages:

```bash
pip install -r requirements.txt
```

Create a `.env` file containing:

```text
GEMINI_API_KEY=YOUR_API_KEY
```

Install Playwright browsers:

```bash
playwright install
```

Run the project:

```bash
python host.py
```

---

## Example Questions

- What is the weather in Jerusalem?
- Weather in Tel Aviv
- מזג האוויר בחיפה
- מה מזג האוויר בבאר שבע?

---

## Notes

- The weather information is retrieved from a live weather website.
- The language model is instructed to answer using the extracted website content.
- The project demonstrates the integration of an LLM with MCP tools and browser automation.

---

## Author

Yisca Nazri
