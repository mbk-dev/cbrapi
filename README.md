
[![Python](https://img.shields.io/badge/python-v3-brightgreen.svg)](https://www.python.org/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/okama.svg)](https://pypi.org/project/okama/)
[![License](https://img.shields.io/pypi/l/okama.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/cbr-api-client)](https://pepy.tech/project/cbr-api-client)

# CBR

_CBR_ is a Python client for the Central Bank of Russia's web services.

## Table of contents

- [CBR main features](##CBR-main-features)
- [Core Functions](##Core Functions)
  - [CURRENCY](###financial-data-and-macroeconomic-indicators)
    - [Get a list of available currencies](####Get a list of available currencies)
    - [Get an internal CBR currency code for a ticker](####Get an internal CBR currency code for a ticker)
    - [Get currency rate historical data](####Get currency rate historical data)
  - [METALS](###financial-data-and-macroeconomic-indicators)
    - [Get precious metals prices time series](####Get precious metals prices time series)
  - [RATES](###financial-data-and-macroeconomic-indicators)
    - [Get the key rate time series](####Get the key rate time series)
    - [Get Interbank Offered Rate and related interbank rates](####Get Interbank Offered Rate and related interbank rates)
  - [RESERVES](###financial-data-and-macroeconomic-indicators)
    - [Get International Reserves and Foreign Currency Liquidity data](####Get International Reserves and Foreign Currency Liquidity data)
  - [RUONIA](###financial-data-and-macroeconomic-indicators)
    - [Get RUONIA time series data](####Get RUONIA time series data)
    - [Get RUONIA index and averages time series](####Get RUONIA index and averages time series)
    - [Get RUONIA overnight value time series](####Get RUONIA overnight value time series)
    - [Get ROISfix time series](####Get ROISfix time series)
- [Installation](##installation)
- [Getting started](##getting-started)
- [License](##getting-started)

## CBR main features
This client provides structured access to the following key data categories from the CBR:  
- CURRENCY: Official exchange rates of foreign currencies against the Russian Ruble.
- METALS: Official prices of precious metals.
- RATES: Key interest rates and interbank lending rates. 
- RESERVES: Data on international reserves and foreign currency liquidity.
- RUONIA: The Russian Overnight Index Average and related benchmark rates.

## Core Functions

### CURRENCY

####Get a list of available currencies

####Get an internal CBR currency code for a ticker

####Get currency rate historical data

### METALS

####Get precious metals prices time series

### RATES

####Get the key rate time series

####Get Interbank Offered Rate and related interbank rates

### RESERVES

####Get International Reserves and Foreign Currency Liquidity data

### RUONIA

####Get RUONIA time series data

####Get RUONIA index and averages time series

####Get RUONIA overnight value time series

####Get ROISfix time series

## Installation

```bash
`pip install cbr-api-client`
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

### 3. Analyze international reserves data
```python
reserves = cbr.get_reserves_data('2023-01-01', '2024-12-31')
print(reserves)
```
![](../images/images/readme4.jpg?raw=true) 

## License

MIT
