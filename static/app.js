(function () {
  'use strict';

  const API_BASE = '';

  function getSymbol() {
    return document.getElementById('symbol').value.trim() || 'RELIANCE';
  }

  function formatPct(value, decimals) {
    if (value == null || Number.isNaN(value)) return '—';
    return (Number(value) * 100).toFixed(decimals != null ? decimals : 1) + '%';
  }

  function formatNum(value, decimals) {
    if (value == null || Number.isNaN(value)) return '—';
    return Number(value).toLocaleString(undefined, {
      minimumFractionDigits: decimals != null ? decimals : 2,
      maximumFractionDigits: decimals != null ? decimals : 2,
    });
  }

  function formatInt(value) {
    if (value == null || Number.isNaN(value)) return '—';
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  function setupTabs() {
    document.querySelectorAll('.tab').forEach((btn) => {
      btn.addEventListener('click', function () {
        const tab = this.dataset.tab;
        document.querySelectorAll('.tab').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach((p) => {
          p.classList.remove('active');
          p.hidden = true;
        });
        this.classList.add('active');
        const panel = document.getElementById('panel-' + tab);
        if (panel) {
          panel.classList.add('active');
          panel.hidden = false;
        }
      });
    });

    document.querySelectorAll('.data-tab').forEach((btn) => {
      btn.addEventListener('click', function () {
        const id = 'data-' + this.dataset.dataTab;
        document.querySelectorAll('.data-tab').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.data-tab-content').forEach((c) => c.classList.remove('active'));
        this.classList.add('active');
        const content = document.getElementById(id);
        if (content) content.classList.add('active');
      });
    });
  }

  function getAnalysisDays() {
    const inputEl = document.getElementById('analysis-lookback-value');
    const unitEl = document.getElementById('analysis-lookback-unit');
    const value = parseInt(inputEl && inputEl.value, 10) || 90;
    const unit = (unitEl && unitEl.value) || 'days';
    const daysPerMonth = 365 / 12;
    const daysPerYear = 365;
    let days = value;
    if (unit === 'months') days = Math.round(value * daysPerMonth);
    if (unit === 'years') days = Math.round(value * daysPerYear);
    return Math.min(Math.max(1, Math.floor(days)), 365 * 15);
  }

  function getRequestedLabel() {
    const value = parseInt(document.getElementById('analysis-lookback-value').value, 10) || 90;
    const unit = document.getElementById('analysis-lookback-unit').value;
    if (unit === 'days') return value + ' days';
    if (unit === 'months') return value + ' months';
    return value + ' years';
  }

  function formatDateRange(dateStr) {
    if (!dateStr || typeof dateStr !== 'string') return '—';
    const d = new Date(dateStr + 'T12:00:00');
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function daysBetween(startStr, endStr) {
    if (!startStr || !endStr) return 0;
    const start = new Date(startStr + 'T12:00:00');
    const end = new Date(endStr + 'T12:00:00');
    return Math.round((end - start) / (24 * 60 * 60 * 1000));
  }

  function formatYearsDays(days) {
    if (days >= 365) return (days / 365).toFixed(1) + ' years';
    return days + ' days';
  }

  function getBacktestParams() {
    return {
      symbol: getSymbol(),
      start: document.getElementById('backtest-start').value,
      end: document.getElementById('backtest-end').value,
      lookback_days: parseInt(document.getElementById('backtest-lookback').value, 10) || 90,
      hold_days: parseInt(document.getElementById('backtest-hold').value, 10) || 5,
      step_days: parseInt(document.getElementById('backtest-step').value, 10) || 5,
    };
  }

  async function fetchJson(url, options = {}) {
    const res = await fetch(url, {
      headers: options.headers || {},
      ...options,
    });
    if (!res.ok) throw new Error(res.statusText || 'Request failed');
    return res.json();
  }

  let priceChart = null;
  let volumeChart = null;
  let rsiChart = null;
  let macdChart = null;
  let equityChart = null;

  function ensureTime(day) {
    const s = typeof day === 'string' ? day : (day && day.date) ? day.date : '';
    return s.substring(0, 10);
  }

  const chartTheme = {
    layout: { background: { type: 'solid', color: '#1e293b' }, textColor: '#94a3b8' },
    grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
    rightPriceScale: { borderColor: '#475569' },
  };

  function buildCandlestickSeries(container) {
    if (priceChart) priceChart.remove();
    const lib = window.lightweightCharts || window.LightweightCharts;
    priceChart = lib.createChart(container, {
      ...chartTheme,
      width: container.clientWidth,
      height: 360,
      autoSize: true,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const series = priceChart.addCandlestickSeries({
      upColor: '#34d399',
      downColor: '#f87171',
      borderVisible: false,
    });
    return { chart: priceChart, series };
  }

  function buildVolumeSeries(container, data) {
    if (volumeChart) volumeChart.remove();
    const lib = window.lightweightCharts || window.LightweightCharts;
    volumeChart = lib.createChart(container, {
      ...chartTheme,
      width: container.clientWidth,
      height: 120,
      autoSize: true,
      timeScale: { visible: true, timeVisible: true, secondsVisible: false },
      rightPriceScale: { visible: false },
    });
    const volSeries = volumeChart.addHistogramSeries({
      color: '#78909c',
      priceFormat: { type: 'volume' },
    });
    volSeries.setData(data);
    volumeChart.timeScale().fitContent();
    return volumeChart;
  }

  function buildLineSeries(container, data, title, color) {
    if (rsiChart) rsiChart.remove();
    const lib = window.lightweightCharts || window.LightweightCharts;
    rsiChart = lib.createChart(container, {
      ...chartTheme,
      width: container.clientWidth,
      height: 140,
      autoSize: true,
      timeScale: { visible: true, timeVisible: true, secondsVisible: false },
    });
    const series = rsiChart.addLineSeries({ color: color || '#2196f3', lineWidth: 2 });
    series.setData(data);
    rsiChart.timeScale().fitContent();
    return rsiChart;
  }

  function buildMacdChart(container, histData, lineData) {
    if (macdChart) macdChart.remove();
    const lib = window.lightweightCharts || window.LightweightCharts;
    macdChart = lib.createChart(container, {
      ...chartTheme,
      width: container.clientWidth,
      height: 140,
      autoSize: true,
      timeScale: { visible: true, timeVisible: true, secondsVisible: false },
    });
    const hist = macdChart.addHistogramSeries({
      color: '#34d399',
      priceFormat: { type: 'custom', formatter: (v) => v.toFixed(4) },
    });
    const line = macdChart.addLineSeries({ color: '#fbbf24', lineWidth: 1 });
    hist.setData(histData);
    line.setData(lineData);
    macdChart.timeScale().fitContent();
    return macdChart;
  }

  function buildEquityChart(container, equityData) {
    if (equityChart) equityChart.remove();
    const lib = window.lightweightCharts || window.LightweightCharts;
    equityChart = lib.createChart(container, {
      ...chartTheme,
      width: container.clientWidth,
      height: 280,
      autoSize: true,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const series = equityChart.addAreaSeries({
      lineColor: '#38bdf8',
      topColor: 'rgba(56, 189, 248, 0.4)',
      bottomColor: 'rgba(56, 189, 248, 0)',
    });
    series.setData(equityData);
    equityChart.timeScale().fitContent();
    return equityChart;
  }

  function deriveSignal(indicators) {
    const rsi = indicators && indicators.rsi;
    const macdHist = indicators && indicators.macd_hist;
    if (rsi != null && rsi < 30 && (macdHist == null || macdHist > 0)) return { action: 'BUY', reason: 'RSI oversold, MACD bullish' };
    if (rsi != null && rsi > 70) return { action: 'SELL', reason: 'RSI overbought' };
    if (macdHist != null && macdHist > 0) return { action: 'BUY', reason: 'MACD bullish' };
    if (macdHist != null && macdHist < 0) return { action: 'SELL', reason: 'MACD bearish' };
    return { action: 'HOLD', reason: 'No strong signal' };
  }

  async function runAnalysis() {
    const symbol = getSymbol();
    const days = getAnalysisDays();
    const loading = document.getElementById('analysis-loading');
    const bodyEl = document.getElementById('analysis-body');
    loading.hidden = false;
    if (bodyEl) bodyEl.hidden = true;
    try {
      const ohlcvRes = await fetchJson(`${API_BASE}/ohlcv?symbol=${encodeURIComponent(symbol)}&days=${days}`);
      const ohlcv = ohlcvRes.ohlcv || [];
      if (!ohlcv.length) {
        loading.textContent = 'No OHLCV data.';
        return;
      }

      const meta = ohlcvRes.raw_fetch_metadata || {};
      const dataStart = meta.data_start_date || (ohlcv[0] && ohlcv[0].date);
      const dataEnd = meta.data_end_date || (ohlcv[ohlcv.length - 1] && ohlcv[ohlcv.length - 1].date);
      const actualDays = daysBetween(dataStart, dataEnd);
      const rangeMsgEl = document.getElementById('analysis-data-range-msg');
      if (rangeMsgEl) {
        const requestedLabel = getRequestedLabel();
        const startFormatted = formatDateRange(dataStart);
        const endFormatted = formatDateRange(dataEnd);
        const actualSpan = formatYearsDays(actualDays);
        if (actualDays < days) {
          rangeMsgEl.innerHTML = 'Data available from <strong>' + startFormatted + '</strong> to <strong>' + endFormatted + '</strong> (' + actualSpan + '). You requested ' + requestedLabel + ' (' + days + ' days).';
          rangeMsgEl.hidden = false;
        } else {
          rangeMsgEl.innerHTML = 'Data from <strong>' + startFormatted + '</strong> to <strong>' + endFormatted + '</strong> (' + requestedLabel + ', ' + ohlcv.length + ' bars).';
          rangeMsgEl.hidden = false;
        }
      }

      const enrichRes = await fetchJson(`${API_BASE}/enrich`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ohlcv, symbol: ohlcvRes.symbol }),
      });
      const sentimentRes = await fetchJson(
        `${API_BASE}/sentiment?symbol=${encodeURIComponent(symbol)}&lookback_days=7`
      );

      const rows = enrichRes.ohlcv_with_indicators || enrichRes.ohlcv || ohlcv;
      const candleData = rows.map((r) => ({
        time: ensureTime(r.date),
        open: Number(r.Open),
        high: Number(r.High),
        low: Number(r.Low),
        close: Number(r.Close),
      }));
      const volData = rows.map((r) => ({
        time: ensureTime(r.date),
        value: Number(r.Volume) || 0,
        color: Number(r.Close) >= Number(r.Open) ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
      }));
      const rsiData = rows
        .filter((r) => r.rsi != null && !Number.isNaN(r.rsi))
        .map((r) => ({ time: ensureTime(r.date), value: Number(r.rsi) }));
      const macdHistData = rows
        .filter((r) => r.macd_hist != null && !Number.isNaN(r.macd_hist))
        .map((r) => ({
          time: ensureTime(r.date),
          value: Number(r.macd_hist),
          color: r.macd_hist >= 0 ? 'rgba(38, 166, 154, 0.6)' : 'rgba(239, 83, 80, 0.6)',
        }));
      const macdLineData = rows
        .filter((r) => r.macd != null && !Number.isNaN(r.macd))
        .map((r) => ({ time: ensureTime(r.date), value: Number(r.macd) }));

      const priceContainer = document.getElementById('chart-price');
      const volContainer = document.getElementById('chart-volume');
      const rsiContainer = document.getElementById('chart-rsi');
      const macdContainer = document.getElementById('chart-macd');

      const { chart, series } = buildCandlestickSeries(priceContainer);
      series.setData(candleData);
      chart.timeScale().fitContent();
      buildVolumeSeries(volContainer, volData);
      if (rsiData.length) buildLineSeries(rsiContainer, rsiData, 'RSI', '#9c27b0');
      if (macdHistData.length && macdLineData.length) buildMacdChart(macdContainer, macdHistData, macdLineData);

      document.getElementById('text-volume-summary').textContent = enrichRes.volume_summary || '—';
      document.getElementById('text-structure-summary').textContent = enrichRes.structure_summary || '—';
      const signal = deriveSignal(enrichRes.indicators);
      const actionEl = document.getElementById('signal-action');
      actionEl.textContent = signal.action;
      actionEl.className = 'signal-action signal-' + signal.action.toLowerCase();
      document.getElementById('signal-reason').textContent = signal.reason || '—';
      document.getElementById('sentiment-score').textContent =
        sentimentRes.score != null ? 'Score: ' + formatNum(sentimentRes.score, 2) : '—';
      document.getElementById('sentiment-label').textContent = (sentimentRes.label || '—').replace(/^\w/, (c) => c.toUpperCase());
      const snippetsList = document.getElementById('sentiment-snippets');
      snippetsList.innerHTML = '';
      (sentimentRes.snippets || []).slice(0, 5).forEach((s) => {
        const li = document.createElement('li');
        li.textContent = s;
        snippetsList.appendChild(li);
      });

      const indTable = document.querySelector('#table-indicators tbody');
      if (indTable) {
        indTable.innerHTML = '';
        const indicators = enrichRes.indicators || {};
        const order = ['sma_20', 'sma_50', 'sma_200', 'ema_12', 'ema_26', 'rsi', 'macd', 'macd_signal', 'macd_hist', 'atr', 'bb_upper', 'bb_lower', 'obv'];
        const labels = { sma_20: 'SMA 20', sma_50: 'SMA 50', sma_200: 'SMA 200', ema_12: 'EMA 12', ema_26: 'EMA 26', rsi: 'RSI', macd: 'MACD', macd_signal: 'MACD Signal', macd_hist: 'MACD Hist', atr: 'ATR', bb_upper: 'BB Upper', bb_lower: 'BB Lower', obv: 'OBV' };
        order.forEach((key) => {
          if (indicators[key] == null) return;
          const tr = document.createElement('tr');
          const label = labels[key] || key.replace(/_/g, ' ');
          const val = indicators[key];
          const display = key === 'obv' ? formatInt(val) : key === 'rsi' ? formatNum(val, 1) : formatNum(val, 2);
          tr.innerHTML = '<td>' + label + '</td><td class="num">' + display + '</td>';
          indTable.appendChild(tr);
        });
        Object.keys(indicators).filter((k) => !order.includes(k)).forEach((key) => {
          const tr = document.createElement('tr');
          tr.innerHTML = '<td>' + key.replace(/_/g, ' ') + '</td><td class="num">' + formatNum(indicators[key], 2) + '</td>';
          indTable.appendChild(tr);
        });
      }

      loading.hidden = true;
      if (bodyEl) bodyEl.hidden = false;
    } catch (e) {
      loading.textContent = 'Error: ' + (e.message || String(e));
      loading.hidden = false;
    }
  }

  async function runBacktest() {
    const params = getBacktestParams();
    const loading = document.getElementById('backtest-loading');
    const resultsEl = document.getElementById('backtest-results');
    loading.hidden = false;
    resultsEl.hidden = true;
    try {
      const res = await fetchJson(`${API_BASE}/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      const rows = res.rows || [];
      const metrics = res.metrics || {};
      const portfolio = metrics.portfolio || {};
      const bySignal = metrics.by_signal || {};
      const strategy = res.strategy || {};

      document.getElementById('backtest-strategy-name').textContent = strategy.name || 'Rule-based';
      document.getElementById('backtest-strategy-desc').textContent = strategy.description || '';
      document.getElementById('backtest-strategy-desc').hidden = !strategy.description;

      let cum = 1;
      const equityData = [];
      const returns = [];
      rows.forEach((r) => {
        let ret = Number(r.forward_return) || 0;
        if (r.action === 'SELL') ret = -ret;
        if (r.action === 'HOLD') ret = 0;
        returns.push(ret);
        cum *= 1 + ret;
        equityData.push({ time: ensureTime(r.date), value: cum });
      });
      if (equityData.length) {
        const container = document.getElementById('chart-equity');
        buildEquityChart(container, equityData);
      }

      document.getElementById('metric-trade-count').textContent = formatInt(portfolio.trade_count);
      document.getElementById('metric-win-rate').textContent = formatPct(portfolio.win_rate, 1);
      document.getElementById('metric-avg-return').textContent = formatPct(portfolio.avg_return, 2);
      document.getElementById('metric-sharpe').textContent = portfolio.sharpe != null ? formatNum(portfolio.sharpe, 2) : '—';
      document.getElementById('metric-max-dd').textContent = formatPct(portfolio.max_drawdown, 2);

      const tbody = document.querySelector('#table-by-signal tbody');
      tbody.innerHTML = '';
      ['BUY', 'SELL', 'HOLD'].forEach((sig) => {
        const s = bySignal[sig] || {};
        const tr = document.createElement('tr');
        tr.innerHTML =
          '<td>' + sig + '</td><td class="num">' + formatInt(s.count) + '</td><td class="num">' + formatPct(s.win_rate, 1) + '</td><td class="num">' + (s.avg_return != null ? formatPct(s.avg_return, 2) : '—') + '</td>';
        tbody.appendChild(tr);
      });
      loading.hidden = true;
      resultsEl.hidden = false;
    } catch (e) {
      loading.textContent = 'Error: ' + (e.message || String(e));
      loading.hidden = false;
    }
  }

  document.getElementById('btn-run-analysis').addEventListener('click', runAnalysis);
  document.getElementById('btn-run-backtest').addEventListener('click', runBacktest);

  setupTabs();
})();
