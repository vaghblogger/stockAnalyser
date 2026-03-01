# Backtest custom rules (indicator formulas)

You can define **BUY** and **SELL** rules using indicators and logical operators, similar to [TradingView Pine Script](https://www.tradingview.com/pine-script-docs/) conditions.

The list of available **indicators**, **flags**, and **operators** is **config-driven**: it is read from `config/config.yaml` under `backtest.rule_schema` (optional). If omitted, the API uses built-in defaults. The web app and any API client fetch the current schema from **GET /backtest/rule-schema** so nothing is hardcoded in the UI.

## Rule structure

Store `buy_rule` and/or `sell_rule` in a strategy’s `params` (when creating/updating a strategy or sending a backtest request with inline params). If both are present, they override the built-in RSI/MACD/SMA rules.

- **Logical:** `and`, `or`, `not` (combine multiple conditions).
- **Comparison operators:** `<`, `<=`, `>`, `>=`, `==`, `!=` (same set as Pine Script).

---

## Condition types

### 1. Indicator vs number

```json
{ "indicator": "rsi", "op": "<", "value": 30 }
```

- **indicator** – key from the list below (e.g. `rsi`, `macd_hist`, `sma_200`).
- **op** – one of: `"<"`, `"<="`, `">"`, `">="`, `"=="`, `"!="`.
- **value** – numeric constant.

### 2. Indicator vs indicator

```json
{ "left": "close", "op": ">", "right": "sma_200" }
```

- **left** / **right** – indicator keys (see below).
- **op** – same comparison operators.

### 3. Flag (boolean)

```json
{ "flag": "above_sma200" }
```

- True if that flag is present on the bar (e.g. price above 200 SMA).
- **flag** – one of the flag names listed below.

### 4. Logical groups

**AND** – all sub-rules must be true:

```json
{ "and": [
  { "indicator": "rsi", "op": "<", "value": 30 },
  { "indicator": "macd_hist", "op": ">", "value": 0 }
]}
```

**OR** – at least one sub-rule true:

```json
{ "or": [
  { "indicator": "rsi", "op": ">", "value": 70 },
  { "flag": "below_sma200" }
]}
```

**NOT**:

```json
{ "not": { "flag": "rsi_overbought" } }
```

You can nest `and` / `or` / `not` arbitrarily.

---

## Available indicators

From `compute_indicators` (last bar values only):

| Key | Description |
|-----|-------------|
| `rsi` | RSI (default 14) |
| `macd` | MACD line |
| `macd_signal` | MACD signal line |
| `macd_hist` | MACD histogram |
| `sma_20`, `sma_50`, `sma_200` | Simple moving averages |
| `ema_12`, `ema_26` | Exponential moving averages |
| `atr` | ATR (default 14) |
| `bb_upper`, `bb_mid`, `bb_lower` | Bollinger Bands |
| `obv` | On-balance volume |
| `close` | Latest close price (injected for rules) |

---

## Available flags

From `pattern_flags` (true if set on current bar):

| Flag | Meaning |
|------|---------|
| `rsi_oversold` | RSI &lt; 30 |
| `rsi_overbought` | RSI &gt; 70 |
| `macd_bullish` | MACD histogram &gt; 0 |
| `macd_bearish` | MACD histogram &lt; 0 |
| `above_sma200` | Close &gt; SMA(200) |
| `below_sma200` | Close &lt; SMA(200) |

---

## Example strategy params

**BUY:** RSI &lt; 30 **and** MACD histogram &gt; 0  

**SELL:** RSI &gt; 70 **or** (below SMA200 **and** MACD bearish)

```json
{
  "buy_rule": {
    "and": [
      { "indicator": "rsi", "op": "<", "value": 30 },
      { "indicator": "macd_hist", "op": ">", "value": 0 }
    ]
  },
  "sell_rule": {
    "or": [
      { "indicator": "rsi", "op": ">", "value": 70 },
      {
        "and": [
          { "flag": "below_sma200" },
          { "flag": "macd_bearish" }
        ]
      }
    ]
  }
}
```

---

## References

- [TradingView Pine Script – Operators](https://www.tradingview.com/pine-script-docs/language/operators/) (logical and comparison operators).
- [Pine Script – Logical operators (and/or)](https://pineify.app/resources/blog/and-logical-operators-in-pine-script) for combining conditions.
