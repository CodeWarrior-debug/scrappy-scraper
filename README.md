# Python Scraper Project

This is a Python web scraper that collects episodes from Christian podcast sources:
1. **Ask Pastor John** episodes from the Desiring God website
2. **Therapy and Theology** episodes by Lysa TerKeurst from Transistor.fm

## Setup

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate  # On macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

You can run the scraper in several ways:

```bash
# Scrape both sources (default)
python src/scraper.py

# Scrape only Ask Pastor John episodes
python src/scraper.py apj

# Scrape only Therapy & Theology episodes  
python src/scraper.py tt

# Scrape both sources explicitly
python src/scraper.py all
```

## Output Files

- `ask_pastor_john.csv` - Contains Ask Pastor John episodes
- `therapy_and_theology.csv` - Contains Therapy & Theology episodes

Both files have the same structure with columns:
- episode_number
- title
- url  
- date
- topic
- description

## Development

- `pytest`: For running tests
- `black`: For code formatting
- `flake8`: For code linting
- `python-dotenv`: For environment variable management

## Project Structure

The project structure will be organized as follows:

```
.
├── README.md
├── requirements.txt
├── src/
│   └── __init__.py
├── tests/
│   └── __init__.py
└── venv/
``` 