# mirror
non-directive weekly research pattern-surfacing layer.

## components
- daily_runner.py: runs at midnight via cron, no llm
- weekly_runner.py: runs sunday midnight via cron, uses chromadb +
  ollama (qwen2.5:32b), writes weekly digest with synthesis and
  generated prompt

## setup
`python3 daily_runner.py`

`python3 weekly_runner.py`

## output
- writes to `../mirror-outputs/daily/YYYY-MM-DD.md`
- writes to `../mirror-outputs/weekly/YYYY-WNN.md`
