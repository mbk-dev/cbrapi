
[![Python](https://img.shields.io/badge/python-v3-brightgreen.svg)](https://www.python.org/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/cbrapi.svg)](https://pypi.org/project/cbrapi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/cbrapi)](https://pepy.tech/project/cbrapi)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# CBRAPI

`cbrapi` is a Python client for the Central Bank of Russia's web services.

## Table of contents

- [CBRAPI main features](#cbr-api-main-features)
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


### 1. Monitor Central Bank's key rate daily changes

```python
import cbrapi as cbr

cbr.get_key_rate("2017-09-13", "2023-09-13").head()
```




    DATE
    2017-09-12    9.0
    2017-09-13    9.0
    2017-09-14    9.0
    2017-09-15    9.0
    2017-09-16    9.0
    Freq: D, Name: KEY_RATE, dtype: float64




### 2. Track precious metals market trends

```python
cbr.get_metals_prices('2024-01-01', '2025-01-31').head()
```




<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>GOLD</th>
      <th>SILVER</th>
      <th>PLATINUM</th>
      <th>PALLADIUM</th>
    </tr>
    <tr>
      <th>DATE</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2024-01-09</th>
      <td>5886.06</td>
      <td>66.40</td>
      <td>2755.41</td>
      <td>2915.27</td>
    </tr>
    <tr>
      <th>2024-01-10</th>
      <td>5848.46</td>
      <td>66.46</td>
      <td>2701.63</td>
      <td>2830.97</td>
    </tr>
    <tr>
      <th>2024-01-11</th>
      <td>5785.30</td>
      <td>65.55</td>
      <td>2654.59</td>
      <td>2845.84</td>
    </tr>
    <tr>
      <th>2024-01-12</th>
      <td>5749.64</td>
      <td>65.26</td>
      <td>2618.17</td>
      <td>2833.52</td>
    </tr>
    <tr>
      <th>2024-01-13</th>
      <td>5749.64</td>
      <td>65.26</td>
      <td>2618.17</td>
      <td>2833.52</td>
    </tr>
  </tbody>
</table>
</div>




### 3. Monitor ROSFIX daily pricing trends
```python
cbr.get_roisfix().head()
```




<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>RATE_1_WEEK</th>
      <th>RATE_2_WEEK</th>
      <th>RATE_1_MONTH</th>
      <th>RATE_2_MONTH</th>
      <th>RATE_3_MONTH</th>
      <th>RATE_6_MONTH</th>
    </tr>
    <tr>
      <th>DATE</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2011-04-14</th>
      <td>3.09</td>
      <td>3.09</td>
      <td>3.18</td>
      <td>3.24</td>
      <td>3.32</td>
      <td>3.51</td>
    </tr>
    <tr>
      <th>2011-04-15</th>
      <td>3.09</td>
      <td>3.09</td>
      <td>3.18</td>
      <td>3.24</td>
      <td>3.32</td>
      <td>3.51</td>
    </tr>
    <tr>
      <th>2011-04-16</th>
      <td>3.09</td>
      <td>3.09</td>
      <td>3.18</td>
      <td>3.24</td>
      <td>3.32</td>
      <td>3.51</td>
    </tr>
    <tr>
      <th>2011-04-17</th>
      <td>3.08</td>
      <td>3.09</td>
      <td>3.19</td>
      <td>3.24</td>
      <td>3.31</td>
      <td>3.50</td>
    </tr>
    <tr>
      <th>2011-04-18</th>
      <td>3.08</td>
      <td>3.09</td>
      <td>3.19</td>
      <td>3.24</td>
      <td>3.31</td>
      <td>3.49</td>
    </tr>
  </tbody>
</table>
</div>




## License

MIT
