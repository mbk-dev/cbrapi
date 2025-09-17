
[![Python](https://img.shields.io/badge/python-v3-brightgreen.svg)](https://www.python.org/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/okama.svg)](https://pypi.org/project/okama/)
[![License](https://img.shields.io/pypi/l/okama.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/cbr-api-client)](https://pepy.tech/project/cbr-api)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# CBR-API

`cbr-api` is a Python client for the Central Bank of Russia's web services.

## Table of contents

- [CBR main features](##cbr-main-features)
- [Core Functions](##core-functions)
  - [CURRENCY](###currency)
    - [Get a list of available currencies](####get-a-list-of-available-currencies)
    - [Get an internal CBR currency code for a ticker](####get-an-internal-cbr-currency-code-for-a-ticker)
    - [Get currency rate historical data](####get-currency-rate-historical-data)
  - [METALS](###metals)
    - [Get precious metals prices time series](####get-precious-metals-prices-time-series)
  - [RATES](###rates)
    - [Get the key rate time series](####get-the-key-rate-time-series)
    - [Get Interbank Offered Rate and related interbank rates](####get-interbank-offered-rate-and-related-interbank-rates)
  - [RESERVES](###reserves)
    - [Get International Reserves and Foreign Currency Liquidity data](####get-international-reserves-and-foreign-currency-liquidity-data)
  - [RUONIA](###ruonia)
    - [Get RUONIA time series data](####get-ruonia-time-series-data)
    - [Get RUONIA index and averages time series](####get-ruonia-index-and-averages-time-series)
    - [Get RUONIA overnight value time series](####get-ruonia-overnight-value-time-series)
    - [Get ROISfix time series](####get-roisfix-time-series)
- [Installation](##installation)
- [Getting started](##getting-started)
- [License](##license)

## CBR main features
This client provides structured access to the following key data categories from the CBR:  
- CURRENCY: Official exchange rates of foreign currencies against the Russian Ruble.
- METALS: Official prices of precious metals.
- RATES: Key interest rates and interbank lending rates. 
- RESERVES: Data on international reserves and foreign currency liquidity.
- RUONIA: The Russian Overnight Index Average and related benchmark rates.

## Core Functions

### CURRENCY

#### Get a list of available currencies
get_currencies_list()

#### Get an internal CBR currency code for a ticker
get_currency_code(ticker: str)

#### Get currency rate historical data
get_time_series(symbol: str, first_date: str, last_date: str, period: str = 'D')  

### METALS

#### Get precious metals prices time series
get_metals_prices(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')  

### RATES

#### Get the key rate time series
get_key_rate(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')  

#### Get Interbank Offered Rate and related interbank rates
get_ibor(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'M')  

### RESERVES

#### Get International Reserves and Foreign Currency Liquidity data
get_mrrf(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'M')  

### RUONIA

#### Get RUONIA time series data
get_ruonia_ts(symbol: str, first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')  

#### Get RUONIA index and averages time series
get_ruonia_index(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')  

#### Get RUONIA overnight value time series
get_ruonia_overnight(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')  

#### Get ROISfix time series
get_roisfix(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')  

## Installation

```bash
`pip install cbr-api`
```

The latest development version can be installed directly from GitHub:

```bash
git clone https://github.com/mbk-dev/cbr.git
cd cbr
poetry install
```

## Getting started

### 1. Get USD/RUB exchange rate with historical data

```python
import okama as ok

usd_rub = cbr.get_currency_rate('USDRUB.CBR', '2024-01-01', '2024-12-31')
print(usd_rub)
```
![](../images/images/readme1.jpg?raw=true) 


### 2. Monitor Central Bank's key rate monthly changes

```python
key_rate = cbr.get_key_rate('2020-01-01', '2024-12-31', period='M')
print(key_rate)
```
![](../images/images/readme2.jpg?raw=true) 


### 3. Track precious metals market trends
```python
metals = cbr.get_metals_prices('2024-01-01', '2025-01-31')
print(metals)
```
![](../images/images/readme3.jpg?raw=true) 

### 4. Analyze international reserves data
```python
reserves = cbr.get_mrrf('2023-01-01', '2024-12-31')
print(reserves)
```
![](../images/images/readme4.jpg?raw=true) 

## License

MIT
