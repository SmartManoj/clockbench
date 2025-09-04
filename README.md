# ClockBench

ClockBench - Visual Reasoning AI Benchmark.

https://clockbench.ai

This is a public dataset that includes 10 clocks, out of 180 clocks available in the private dataset.
Full dataset if intentionally kept private in order to avoid data leaking into models training.

## Setup Instructions

Install dependencies declared in pyproject.toml

```bash
pip install -e .
```
The script depends on `requests`. If you prefer not to use `pip install -e .`, you can alternatively run `pip install requests` directly.

## Run Instructions
Benchmark includes two scripts designed to be run consecutively:

```bash
python3 clockbench_evaluate.py
```
This script runs an evaluation of a chosen model via OpenRouter API. Please add your API key and specify a model to evaluate in the leading section of the script.
Script outputs the results in a JSON file.

```bash
python3 clockbench_grade.py
```
This script grades the results.
Script outputs the results in a JSON file.

## Contributing

Pull requests are welcome.