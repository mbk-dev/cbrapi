
[![Python](https://img.shields.io/badge/python-v3-brightgreen.svg)](https://www.python.org/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/okama.svg)](https://pypi.org/project/cbrapi/)
[![License](https://img.shields.io/pypi/l/okama.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/cbr-api-client)](https://pepy.tech/project/cbrapi)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# CBRAPI

`cbrapi` is a Python client for the Central Bank of Russia's web services.

## Table of contents

- [CBR-API main features](#cbr-api-main-features)
- [Core Functions](#core-functions)
  - [CURRENCY](#currency)
  - [METALS](#metals)
  - [RATES](#rates)
  - [RESERVES](#reserves)
  - [RUONIA](#ruonia)
- [Getting started](#getting-started)
- [License](#license)

## CBRAPI main features
This client provides structured access to the following key data categories from the CBR:  
- CURRENCY: Official exchange rates of foreign currencies against the Russian Ruble.
- METALS: Official prices of precious metals.
- RATES: Key interest rates and interbank lending rates. 
- RESERVES: Data on international reserves and foreign currency liquidity.
- RUONIA: The Russian Overnight Index Average and related benchmark rates.

## Core Functions

### CURRENCY

#### Get a list of available currencies
Returns a list of all available currency tickers supported by the API.  
`get_currencies_list()`  

#### Get an internal CBR currency code for a ticker
Retrieves the internal CBR currency code for a given currency ticker.  
`get_currency_code(ticker: str)`  

#### Get currency rate historical data
Fetches historical exchange rate data for a specified currency and date range.  
`get_time_series(symbol: str, first_date: str, last_date: str, period: str = 'D')`  

### METALS

#### Get precious metals prices time series
Provides historical prices for precious metals (Gold, Silver, Platinum, Palladium).  
`get_metals_prices(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')`  

### RATES

IBOR: Interbank Offered Rate.  

#### Get the key rate time series
Retrieves the historical key rate set by the Central Bank of Russia.  
`get_key_rate(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')`  

#### Get Interbank Offered Rate and related interbank rates
Fetches the historical Interbank Offered Rate and related interbank rates.  
`get_ibor(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'M')`  

### RESERVES

MRRF: International Reserves and Foreign Currency Liquidity.  

#### Get International Reserves and Foreign Currency Liquidity data
Provides time series data for International Reserves and Foreign Currency Liquidity.  
`get_mrrf(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'M')`  

### RUONIA

RUONIA: Russian Overnight Index Average.  
ROISfix: Russian Overnight Index Swap Fixing.  

#### Get RUONIA time series data
Retrieves RUONIA time series data for a specific symbol.  
`get_ruonia_ts(symbol: str, first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')`  

#### Get RUONIA index and averages time series
Fetches the historical RUONIA index and averages.  
`get_ruonia_index(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')`  

#### Get RUONIA overnight value time series
Provides the historical RUONIA overnight value.  
`get_ruonia_overnight(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')`  

#### Get ROISfix time series
Retrieves the historical ROISfix time series data.  
`get_roisfix(first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = 'D')`  

## Installation

```bash
pip install cbrapi
```

The latest development version can be installed directly from GitHub:

```bash
git clone https://github.com/mbk-dev/cbrapi.git
cd cbrapi
poetry install
```

## Getting started


### 1. Get USD/RUB exchange rate with historical data

```python
import cbrapi as cbr

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
