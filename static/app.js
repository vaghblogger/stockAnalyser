(function () {
  'use strict';

  const API_BASE = '';

  function getSymbol() {
    var analysisInput = document.getElementById('analysis-symbol-input');
    if (analysisInput && analysisInput.value && analysisInput.value.trim()) {
      return analysisInput.value.trim();
    }
    return 'RELIANCE';
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

  var dashboardViewId = null;
  var dashboardColumnsConfig = null;
  var DASHBOARD_AVAILABLE_COLUMNS = [
    { key: 'stock', label: 'Stock', alwaysShow: true },
    { key: 'close', label: 'Close', alwaysShow: false },
    { key: 'sma_20', label: 'SMA 20', alwaysShow: false },
    { key: 'sma_50', label: 'SMA 50', alwaysShow: false },
    { key: 'sma_200', label: 'SMA 200', alwaysShow: false },
    { key: 'rsi', label: 'RSI', alwaysShow: false },
    { key: 'macd_hist', label: 'MACD Hist', alwaysShow: false },
    { key: 'atr', label: 'ATR', alwaysShow: false },
    { key: 'signal', label: 'Signal', alwaysShow: false },
    { key: 'reason', label: 'Reason', alwaysShow: false },
  ];
  function getDefaultDashboardColumns() {
    return [
      { key: 'stock', visible: true, order: 0 },
      { key: 'close', visible: true, order: 1 },
      { key: 'sma_20', visible: true, order: 2 },
      { key: 'sma_50', visible: true, order: 3 },
      { key: 'rsi', visible: true, order: 4 },
      { key: 'macd_hist', visible: true, order: 5 },
      { key: 'signal', visible: true, order: 6 },
      { key: 'reason', visible: true, order: 7 },
    ];
  }
  function getDashboardColumnsConfig() {
    if (dashboardColumnsConfig && dashboardColumnsConfig.length) return dashboardColumnsConfig;
    return getDefaultDashboardColumns();
  }
  function buildDashboardHeader(columnsConfig) {
    var thead = document.getElementById('dashboard-thead');
    if (!thead) return;
    var tr = thead.querySelector('tr') || document.createElement('tr');
    tr.innerHTML = '';
    var visible = columnsConfig.filter(function (c) { return c.visible; }).sort(function (a, b) { return (a.order - b.order); });
    visible.forEach(function (c) {
      var th = document.createElement('th');
      var label = c.key === 'stock' ? 'Stock' : (DASHBOARD_AVAILABLE_COLUMNS.find(function (x) { return x.key === c.key; }) || {}).label || c.key;
      th.textContent = label;
      if (c.key !== 'stock' && c.key !== 'signal' && c.key !== 'reason') th.className = 'num';
      tr.appendChild(th);
    });
    var thActions = document.createElement('th');
    thActions.textContent = 'Actions';
    thActions.className = 'dashboard-actions-col';
    tr.appendChild(thActions);
    if (!thead.querySelector('tr')) thead.appendChild(tr);
  }
  async function ensureDashboardView() {
    if (dashboardViewId) return;
    try {
      var res = await fetchJson(API_BASE + '/api/dashboard/views');
      var views = (res && res.views) ? res.views : [];
      if (views.length > 0) {
        dashboardViewId = views[0].id;
        dashboardColumnsConfig = (views[0].columns_config && views[0].columns_config.length) ? views[0].columns_config : getDefaultDashboardColumns();
        return;
      }
      var defaultCols = getDefaultDashboardColumns();
      var createRes = await fetchJson(API_BASE + '/api/dashboard/views', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Default', columns_config: defaultCols }),
      });
      if (createRes && createRes.id) {
        dashboardViewId = createRes.id;
        dashboardColumnsConfig = defaultCols;
      }
    } catch (e) {
      console.warn('Dashboard views fetch failed, using default columns', e);
      dashboardColumnsConfig = getDefaultDashboardColumns();
    }
  }

  // --- Indicator strength interpretation (strong / weak / neutral) ---
  function interpretRSI(rsi) {
    if (rsi == null || Number.isNaN(rsi)) return { label: '—', strength: 'neutral' };
    var r = Number(rsi);
    if (r >= 70) return { label: 'Overbought', strength: 'weak' };
    if (r <= 30) return { label: 'Oversold', strength: 'strong' };
    if (r >= 55) return { label: 'Bullish', strength: 'strong' };
    if (r <= 45) return { label: 'Bearish', strength: 'weak' };
    return { label: 'Neutral', strength: 'neutral' };
  }
  function interpretTrend(close, sma20, sma50, sma200) {
    if (close == null || Number.isNaN(close)) return { label: '—', strength: 'neutral' };
    var c = Number(close);
    var s20 = sma20 != null && !Number.isNaN(sma20) ? Number(sma20) : null;
    var s50 = sma50 != null && !Number.isNaN(sma50) ? Number(sma50) : null;
    var s200 = sma200 != null && !Number.isNaN(sma200) ? Number(sma200) : null;
    if (s20 != null && s50 != null && s200 != null) {
      if (c > s20 && s20 > s50 && s50 > s200) return { label: 'Strong uptrend', strength: 'strong' };
      if (c > s20 && s20 > s50) return { label: 'Uptrend', strength: 'strong' };
      if (c < s20 && s20 < s50 && s50 < s200) return { label: 'Strong downtrend', strength: 'weak' };
      if (c < s20 && s20 < s50) return { label: 'Downtrend', strength: 'weak' };
      if (c > s200) return { label: 'Above long-term', strength: 'strong' };
      if (c < s200) return { label: 'Below long-term', strength: 'weak' };
    }
    if (s20 != null && c > s20) return { label: 'Above SMA 20', strength: 'strong' };
    if (s20 != null && c < s20) return { label: 'Below SMA 20', strength: 'weak' };
    return { label: '—', strength: 'neutral' };
  }
  function interpretMACD(hist) {
    if (hist == null || Number.isNaN(hist)) return { label: '—', strength: 'neutral' };
    var h = Number(hist);
    if (h > 0) return { label: 'Bullish', strength: h > 1 ? 'strong' : 'neutral' };
    return { label: 'Bearish', strength: h < -1 ? 'weak' : 'neutral' };
  }
  function interpretATR(atr, close) {
    if (atr == null || close == null || Number.isNaN(atr) || Number.isNaN(close) || close === 0) return { label: '—', strength: 'neutral' };
    var pct = (Number(atr) / Number(close)) * 100;
    if (pct >= 3) return { label: 'High (' + formatNum(pct, 1) + '% of price)', strength: 'weak' };
    if (pct <= 1) return { label: 'Low', strength: 'strong' };
    return { label: 'Normal', strength: 'neutral' };
  }
  function interpretBB(close, upper, lower) {
    if (close == null || upper == null || lower == null) return { label: '—', strength: 'neutral' };
    var c = Number(close); var u = Number(upper); var l = Number(lower);
    if (c >= u * 0.99) return { label: 'Near upper band', strength: 'weak' };
    if (c <= l * 1.01) return { label: 'Near lower band', strength: 'strong' };
    return { label: 'Mid range', strength: 'neutral' };
  }

  function closeAllModals() {
    var dashboardModal = document.getElementById('dashboard-columns-modal');
    var saveStrategyModal = document.getElementById('save-strategy-modal');
    var addStrategyModal = document.getElementById('add-strategy-modal');
    var addStockModal = document.getElementById('add-stock-modal');
    var editStockModal = document.getElementById('edit-stock-modal');
    if (dashboardModal) dashboardModal.hidden = true;
    if (saveStrategyModal) saveStrategyModal.hidden = true;
    if (addStrategyModal) addStrategyModal.hidden = true;
    if (addStockModal) addStockModal.hidden = true;
    if (editStockModal) editStockModal.hidden = true;
  }

  function setupTabs() {
    var tabList = document.querySelector('.tabs');
    if (tabList) {
      tabList.addEventListener('click', function (ev) {
        var btn = ev.target;
        while (btn && btn !== tabList) {
          if (btn.classList && btn.classList.contains('tab')) {
            ev.preventDefault();
            var tab = btn.getAttribute('data-tab');
            if (tab) {
              closeAllModals();
              var tabs = document.querySelectorAll('.tab');
              for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove('active');
              var panels = document.querySelectorAll('.tab-panel');
              for (var j = 0; j < panels.length; j++) {
                panels[j].classList.remove('active');
                panels[j].setAttribute('hidden', '');
              }
              btn.classList.add('active');
              var panel = document.getElementById('panel-' + tab);
              if (panel) {
                panel.classList.add('active');
                panel.removeAttribute('hidden');
              }
              if (tab === 'dashboard') loadDashboard();
              else if (tab === 'backtest') loadBacktestStrategies();
              else if (tab === 'paper') loadPaperPortfolios();
              else if (tab === 'strategies') loadStrategiesTab();
            }
            return;
          }
          btn = btn.parentNode;
        }
      });
    }

    var dataTabContainer = document.querySelector('.data-tabs');
    if (dataTabContainer) {
      dataTabContainer.addEventListener('click', function (ev) {
        var btn = ev.target;
        while (btn && btn !== dataTabContainer) {
          if (btn.classList && btn.classList.contains('data-tab')) {
            var id = 'data-' + (btn.getAttribute('data-data-tab') || '');
            if (id && id !== 'data-') {
              var dataTabs = document.querySelectorAll('.data-tab');
              for (var i = 0; i < dataTabs.length; i++) dataTabs[i].classList.remove('active');
              var contents = document.querySelectorAll('.data-tab-content');
              for (var k = 0; k < contents.length; k++) contents[k].classList.remove('active');
              btn.classList.add('active');
              var content = document.getElementById(id);
              if (content) content.classList.add('active');
            }
            return;
          }
          btn = btn.parentNode;
        }
      });
    }
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
    var symbolsEl = document.getElementById('backtest-symbols');
    var symbolsStr = (symbolsEl && symbolsEl.value) ? symbolsEl.value.trim() : getSymbol();
    var symbols = symbolsStr.split(/[\s,]+/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (symbols.length === 0) symbols = [getSymbol()];
    var strategyEl = document.getElementById('backtest-strategy');
    var strategyId = (strategyEl && strategyEl.value) ? strategyEl.value : null;
    return {
      symbols: symbols,
      symbol: symbols[0],
      strategy_id: strategyId || undefined,
      start: document.getElementById('backtest-start').value,
      end: document.getElementById('backtest-end').value,
      lookback_days: parseInt(document.getElementById('backtest-lookback').value, 10) || 90,
      hold_days: parseInt(document.getElementById('backtest-hold').value, 10) || 5,
      step_days: parseInt(document.getElementById('backtest-step').value, 10) || 5,
    };
  }
  async function loadBacktestStrategies() {
    var sel = document.getElementById('backtest-strategy');
    if (!sel) return;
    try {
      var res = await fetchJson(API_BASE + '/api/strategies');
      var list = (res && res.strategies) ? res.strategies : [];
      sel.innerHTML = '<option value="">Global default</option>';
      list.forEach(function (s) {
        var opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name + (s.is_global_default ? ' (default)' : '');
        sel.appendChild(opt);
      });
    } catch (e) {
      console.warn('Failed to load strategies', e);
    }
  }

  async function fetchJson(url, options = {}) {
    const res = await fetch(url, {
      headers: options.headers || {},
      ...options,
    });
    if (!res.ok) throw new Error(res.statusText || 'Request failed');
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch (e) {
      console.warn('fetchJson: response was not JSON. Content-Type:', res.headers.get('Content-Type'), 'body length:', text.length);
      throw new Error('Invalid JSON response');
    }
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

  function clearAnalysisDataPanel() {
    const el = (id) => document.getElementById(id);
    if (el('text-volume-summary')) el('text-volume-summary').textContent = '—';
    if (el('text-structure-summary')) el('text-structure-summary').textContent = '—';
    if (el('signal-action')) { el('signal-action').textContent = '—'; el('signal-action').className = 'signal-action'; }
    if (el('signal-reason')) el('signal-reason').textContent = '—';
    var banner = el('signal-banner');
    if (banner) {
      banner.className = 'signal-banner';
      if (el('signal-banner-action')) el('signal-banner-action').textContent = '—';
      if (el('signal-banner-reason')) el('signal-banner-reason').textContent = '';
    }
    if (el('sentiment-source')) el('sentiment-source').textContent = '';
    if (el('sentiment-score')) el('sentiment-score').textContent = '—';
    if (el('sentiment-label')) { el('sentiment-label').textContent = '—'; el('sentiment-label').className = 'sentiment-label-badge'; }
    const snippetsList = el('sentiment-snippets');
    if (snippetsList) snippetsList.innerHTML = '';
    var indSummary = document.getElementById('indicator-summary');
    if (indSummary) indSummary.textContent = '—';
    ['indicator-trend', 'indicator-momentum', 'indicator-volatility', 'indicator-volume'].forEach(function (id) {
      var container = document.getElementById(id);
      if (container) container.innerHTML = '';
    });
    var gaugeEl = document.getElementById('indicator-gauges');
    if (gaugeEl) gaugeEl.innerHTML = '';
  }

  function formatSentimentSource(source) {
    if (!source || typeof source !== 'string') return 'News sentiment';
    var s = source.trim().toLowerCase();
    if (s === 'free_news_finbert') return 'News headlines · FinBERT';
    return source.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function parseSnippetForDisplay(text) {
    if (text == null || typeof text !== 'string') return '';
    var t = text.replace(/\s+/g, ' ').trim();
    var maxLen = 220;
    if (t.length <= maxLen) return t;
    var lastSpace = t.lastIndexOf(' ', maxLen);
    var cut = lastSpace > 160 ? t.substring(0, lastSpace) : t.substring(0, maxLen);
    return cut + '…';
  }

  function renderGaugeSemicircle(parentEl, title, value, minVal, maxVal, zones, valueLabel, labelText) {
    var pct = (Number(value) - minVal) / (maxVal - minVal || 1);
    pct = Math.max(0, Math.min(1, pct));
    var angleDeg = 180 - pct * 180;
    var angleRad = (angleDeg * Math.PI) / 180;
    var cx = 50; var cy = 50; var r = 38;
    var needleX = cx + r * Math.cos(angleRad);
    var needleY = cy - r * Math.sin(angleRad);
    var zonePath = '';
    zones.forEach(function (z) {
      var startPct = (z.lo - minVal) / (maxVal - minVal || 1);
      var endPct = (z.hi - minVal) / (maxVal - minVal || 1);
      var a1 = 180 - Math.max(0, Math.min(1, startPct)) * 180;
      var a2 = 180 - Math.max(0, Math.min(1, endPct)) * 180;
      var rad1 = (a1 * Math.PI) / 180; var rad2 = (a2 * Math.PI) / 180;
      var x1 = cx + r * Math.cos(rad1); var y1 = cy - r * Math.sin(rad1);
      var x2 = cx + r * Math.cos(rad2); var y2 = cy - r * Math.sin(rad2);
      var large = (a2 - a1) > 180 ? 1 : 0;
      zonePath += '<path d="M ' + cx + ' ' + cy + ' L ' + x1 + ' ' + y1 + ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x2 + ' ' + y2 + ' Z" class="' + (z.className || '') + '"/>';
    });
    var html = '<div class="gauge-wrap"><div class="gauge-title">' + escapeHtml(title) + '</div><svg viewBox="0 0 100 60" width="120" height="72">' +
      zonePath +
      '<line x1="' + cx + '" y1="' + cy + '" x2="' + needleX + '" y2="' + needleY + '" stroke="var(--text)" stroke-width="2" class="gauge-needle"/>' +
      '</svg><div class="gauge-value">' + (valueLabel != null ? valueLabel : (value != null ? Number(value).toFixed(2) : '—')) + '</div><div class="gauge-label">' + (labelText || '') + '</div></div>';
    var wrap = document.createElement('div');
    wrap.innerHTML = html;
    parentEl.appendChild(wrap.firstElementChild || wrap);
  }
  function renderIndicatorGauges(indicators, interpretations, signal) {
    var el = document.getElementById('indicator-gauges');
    if (!el) return;
    var close = indicators.close;
    var trendInterp = interpretations.trend;
    var rsiInterp = interpretations.rsi;
    var macdInterp = interpretations.macd;
    var atrInterp = interpretations.atr;
    var bbInterp = interpretations.bb;
    el.innerHTML = '';
    function addGauge(title, value, minVal, maxVal, zones, valueLabel, labelText) {
      renderGaugeSemicircle(el, title, value, minVal, maxVal, zones, valueLabel, labelText);
    }
    if (indicators.rsi != null && !Number.isNaN(indicators.rsi)) {
      addGauge('RSI', indicators.rsi, 0, 100,
        [{ lo: 0, hi: 30, className: 'gauge-zone-buy' }, { lo: 30, hi: 70, className: 'gauge-zone-hold' }, { lo: 70, hi: 100, className: 'gauge-zone-sell' }],
        indicators.rsi != null ? Number(indicators.rsi).toFixed(1) : '—', rsiInterp && rsiInterp.label ? rsiInterp.label : '');
    }
    var macdVal = indicators.macd_hist;
    if (macdVal != null && !Number.isNaN(macdVal)) {
      var mMin = -2; var mMax = 2;
      if (Math.abs(macdVal) > 2) { mMin = Math.min(mMin, macdVal); mMax = Math.max(mMax, macdVal); }
      addGauge('MACD Hist', macdVal, mMin, mMax,
        [{ lo: mMin, hi: 0, className: 'gauge-zone-sell' }, { lo: 0, hi: mMax, className: 'gauge-zone-buy' }],
        macdVal != null ? Number(macdVal).toFixed(3) : '—', macdInterp && macdInterp.label ? macdInterp.label : '');
    }
    var trendVal = (trendInterp && trendInterp.strength === 'strong') ? 75 : (trendInterp && trendInterp.strength === 'weak') ? 25 : 50;
    addGauge('Trend', trendVal, 0, 100,
      [{ lo: 0, hi: 40, className: 'gauge-zone-sell' }, { lo: 40, hi: 60, className: 'gauge-zone-hold' }, { lo: 60, hi: 100, className: 'gauge-zone-buy' }],
      null, trendInterp && trendInterp.label ? trendInterp.label : '');
    if (indicators.atr != null && close != null && close > 0) {
      var atrPct = (indicators.atr / close) * 100;
      addGauge('ATR %', Math.min(10, atrPct), 0, 10,
        [{ lo: 0, hi: 1, className: 'gauge-zone-buy' }, { lo: 1, hi: 3, className: 'gauge-zone-hold' }, { lo: 3, hi: 10, className: 'gauge-zone-sell' }],
        atrPct.toFixed(2) + '%', atrInterp && atrInterp.label ? atrInterp.label : '');
    }
    var summaryVal = signal && signal.action === 'BUY' ? 80 : (signal && signal.action === 'SELL' ? 20 : 50);
    addGauge('Signal', summaryVal, 0, 100,
      [{ lo: 0, hi: 33, className: 'gauge-zone-sell' }, { lo: 33, hi: 66, className: 'gauge-zone-hold' }, { lo: 66, hi: 100, className: 'gauge-zone-buy' }],
      null, signal && signal.action ? signal.action : 'HOLD');
  }

  async function runAnalysis() {
    const symbol = getSymbol();
    const days = getAnalysisDays();
    const loading = document.getElementById('analysis-loading');
    const bodyEl = document.getElementById('analysis-body');
    loading.hidden = false;
    loading.textContent = 'Loading…';
    if (bodyEl) bodyEl.hidden = true;
    clearAnalysisDataPanel();
    try {
      // Always fetch latest: backend updates cache then returns data for analysis
      const ohlcvRes = await fetchJson(`${API_BASE}/ohlcv?symbol=${encodeURIComponent(symbol)}&days=${days}&use_cache=false`);
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
          rangeMsgEl.innerHTML = 'Data from <strong>' + startFormatted + '</strong> to <strong>' + endFormatted + '</strong> (' + actualSpan + ', ' + ohlcv.length + ' bars). You requested ' + requestedLabel + '. The source returned only this range; run again with a shorter lookback or try another symbol if you need more history.';
          rangeMsgEl.hidden = false;
        } else {
          rangeMsgEl.innerHTML = 'Data from <strong>' + startFormatted + '</strong> to <strong>' + endFormatted + '</strong> (' + requestedLabel + ', ' + ohlcv.length + ' bars).';
          rangeMsgEl.hidden = false;
        }
      }

      let enrichRes = await fetchJson(`${API_BASE}/enrich`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ohlcv, symbol: ohlcvRes.symbol }),
      });
      // Defensive: if server double-encoded JSON, response can be a string
      if (typeof enrichRes === 'string') {
        try {
          enrichRes = JSON.parse(enrichRes);
        } catch (e) {
          console.warn('Enrich response was string, parse failed:', e);
        }
      }
      var sentimentUrl = `${API_BASE}/sentiment?symbol=${encodeURIComponent(symbol)}&lookback_days=7`;
      if (ohlcvRes.company_name) sentimentUrl += '&company_name=' + encodeURIComponent(ohlcvRes.company_name);
      const sentimentRes = await fetchJson(sentimentUrl);

      const rows = (enrichRes && Array.isArray(enrichRes.ohlcv_with_indicators)) ? enrichRes.ohlcv_with_indicators : (enrichRes && enrichRes.ohlcv) || ohlcv;
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

      var volEl = document.getElementById('text-volume-summary');
      var structEl = document.getElementById('text-structure-summary');
      if (volEl) volEl.textContent = (enrichRes && enrichRes.volume_summary != null) ? String(enrichRes.volume_summary) : '—';
      if (structEl) structEl.textContent = (enrichRes && enrichRes.structure_summary != null) ? String(enrichRes.structure_summary) : '—';

      // Collect indicators: prefer API top-level, then last row of enriched data (so we always have a source)
      var indKeys = ['sma_20', 'sma_50', 'sma_200', 'ema_12', 'ema_26', 'rsi', 'macd', 'macd_signal', 'macd_hist', 'atr', 'bb_upper', 'bb_lower', 'obv', 'close'];
      var indicators = {};
      if (enrichRes && enrichRes.indicators && typeof enrichRes.indicators === 'object') {
        indKeys.forEach(function (k) {
          var v = enrichRes.indicators[k];
          if (v != null && v !== '' && !Number.isNaN(Number(v))) indicators[k] = Number(v);
        });
        Object.keys(enrichRes.indicators).forEach(function (k) {
          if (indKeys.indexOf(k) === -1) {
            var v = enrichRes.indicators[k];
            if (v != null && v !== '' && !Number.isNaN(Number(v))) indicators[k] = Number(v);
          }
        });
      }
      if (rows.length > 0) {
        var lastRow = rows[rows.length - 1];
        indKeys.forEach(function (k) {
          if (indicators[k] != null && !Number.isNaN(indicators[k])) return;
          var v = lastRow[k];
          if (v != null && v !== '' && !Number.isNaN(Number(v))) indicators[k] = Number(v);
        });
        // Fallback: last row may use 'Close' for close price
        if ((indicators.close == null || Number.isNaN(indicators.close)) && lastRow.Close != null && !Number.isNaN(Number(lastRow.Close))) {
          indicators.close = Number(lastRow.Close);
        }
      }
      Object.keys(indicators).forEach(function (k) {
        var v = indicators[k];
        indicators[k] = (v != null && v !== '' && !Number.isNaN(Number(v))) ? Number(v) : null;
      });
      var hasAnyIndicator = indKeys.some(function (k) { return indicators[k] != null && !Number.isNaN(indicators[k]); });
      if (!hasAnyIndicator && rows.length > 0) {
        console.warn('[indicators] No values: enrichRes.indicators?', !!enrichRes && !!enrichRes.indicators, 'rows[0] keys:', enrichRes && enrichRes.ohlcv_with_indicators && enrichRes.ohlcv_with_indicators[0] ? Object.keys(enrichRes.ohlcv_with_indicators[0]) : (rows[0] ? Object.keys(rows[0]) : []));
      }
      const signal = deriveSignal(indicators);
      const actionEl = document.getElementById('signal-action');
      if (actionEl) {
        actionEl.textContent = signal.action;
        actionEl.className = 'signal-action signal-' + signal.action.toLowerCase();
      }
      var reasonEl = document.getElementById('signal-reason');
      if (reasonEl) reasonEl.textContent = signal.reason || '—';
      // Signal banner upfront
      var bannerAction = document.getElementById('signal-banner-action');
      var bannerReason = document.getElementById('signal-banner-reason');
      var bannerEl = document.getElementById('signal-banner');
      if (bannerAction) bannerAction.textContent = signal.action;
      if (bannerReason) bannerReason.textContent = signal.reason || '';
      if (bannerEl) {
        bannerEl.className = 'signal-banner signal-banner-' + signal.action.toLowerCase();
      }
      // Sentiment: source, score, label, readable snippets
      var sourceEl = document.getElementById('sentiment-source');
      if (sourceEl) sourceEl.textContent = sentimentRes && sentimentRes.source ? formatSentimentSource(sentimentRes.source) : 'News sentiment';
      var scoreEl = document.getElementById('sentiment-score');
      if (scoreEl) scoreEl.textContent = sentimentRes && sentimentRes.score != null ? formatNum(sentimentRes.score, 2) : '—';
      var labelEl = document.getElementById('sentiment-label');
      if (labelEl) {
        var lbl = (sentimentRes && sentimentRes.label ? sentimentRes.label : '—').replace(/^\w/, function (c) { return c.toUpperCase(); });
        labelEl.textContent = lbl;
        labelEl.className = 'sentiment-label-badge ' + (sentimentRes && sentimentRes.label ? sentimentRes.label.toLowerCase() : 'neutral');
      }
      const snippetsList = document.getElementById('sentiment-snippets');
      if (snippetsList) {
        snippetsList.innerHTML = '';
        var rawSnippets = (sentimentRes && sentimentRes.snippets ? sentimentRes.snippets : []).slice(0, 5);
        if (rawSnippets.length === 0) {
          var emptyLi = document.createElement('li');
          emptyLi.textContent = 'No recent headlines for this symbol.';
          emptyLi.className = 'sentiment-empty';
          snippetsList.appendChild(emptyLi);
        } else {
          rawSnippets.forEach(function (s) {
            var display = parseSnippetForDisplay(s);
            if (!display) return;
            var li = document.createElement('li');
            li.textContent = display;
            snippetsList.appendChild(li);
          });
        }
      }

      // Redesigned indicator panel: summary line + grouped sections with strength badges
      var indSummaryEl = document.getElementById('indicator-summary');
      var indTrendEl = document.getElementById('indicator-trend');
      var indMomentumEl = document.getElementById('indicator-momentum');
      var indVolatilityEl = document.getElementById('indicator-volatility');
      var indVolumeEl = document.getElementById('indicator-volume');
      var close = indicators.close != null ? indicators.close : (rows.length > 0 && rows[rows.length - 1].Close != null ? Number(rows[rows.length - 1].Close) : null);
      if (rows.length && close == null) close = Number(rows[rows.length - 1].Close);
      var trendInterp = interpretTrend(close, indicators.sma_20, indicators.sma_50, indicators.sma_200);
      var rsiInterp = interpretRSI(indicators.rsi);
      var macdInterp = interpretMACD(indicators.macd_hist);
      var atrInterp = interpretATR(indicators.atr, close);
      var bbInterp = interpretBB(close, indicators.bb_upper, indicators.bb_lower);
      if (indSummaryEl) {
        var parts = [];
        parts.push('Trend: ' + trendInterp.label);
        parts.push('RSI: ' + rsiInterp.label);
        parts.push('MACD: ' + macdInterp.label);
        indSummaryEl.textContent = parts.join(' · ');
      }
      renderIndicatorGauges(indicators, { trend: trendInterp, rsi: rsiInterp, macd: macdInterp, atr: atrInterp, bb: bbInterp }, signal);
      function addIndRow(container, label, val, interpret) {
        if (!container) return;
        var interp = interpret ? interpret(val) : null;
        var display = (val == null || Number.isNaN(val)) ? (interp && interp.label ? interp.label : '—') : (typeof val === 'number' && val % 1 === 0 && val > 1000 ? formatInt(val) : formatNum(val, 2));
        if (label === 'RSI' && val != null) display = formatNum(val, 1);
        var strength = interp && interp.strength ? interp.strength : 'neutral';
        var showBadge = interp && interp.label && label !== 'Trend';
        var row = document.createElement('div');
        row.className = 'indicator-row';
        row.innerHTML = '<span class="indicator-name">' + label + '</span><span class="indicator-value">' + display + '</span>' + (showBadge ? '<span class="indicator-badge indicator-badge-' + strength + '">' + interp.label + '</span>' : '');
        container.appendChild(row);
      }
      function addIndRowBB(container, label, val) {
        if (!container) return;
        var display = (val == null || Number.isNaN(val)) ? '—' : formatNum(val, 2);
        var row = document.createElement('div');
        row.className = 'indicator-row';
        row.innerHTML = '<span class="indicator-name">' + label + '</span><span class="indicator-value">' + display + '</span>';
        container.appendChild(row);
      }
      if (indTrendEl) {
        indTrendEl.innerHTML = '';
        addIndRow(indTrendEl, 'Price (Close)', close, null);
        addIndRow(indTrendEl, 'SMA 20', indicators.sma_20, null);
        addIndRow(indTrendEl, 'SMA 50', indicators.sma_50, null);
        addIndRow(indTrendEl, 'SMA 200', indicators.sma_200, null);
        addIndRow(indTrendEl, 'Trend', null, function () { return trendInterp; });
      }
      if (indMomentumEl) {
        indMomentumEl.innerHTML = '';
        addIndRow(indMomentumEl, 'RSI', indicators.rsi, function (v) { return interpretRSI(v); });
        addIndRow(indMomentumEl, 'MACD', indicators.macd, null);
        addIndRow(indMomentumEl, 'MACD Signal', indicators.macd_signal, null);
        addIndRow(indMomentumEl, 'MACD Hist', indicators.macd_hist, function (v) { return interpretMACD(v); });
      }
      if (indVolatilityEl) {
        indVolatilityEl.innerHTML = '';
        addIndRow(indVolatilityEl, 'ATR', indicators.atr, function (v) { return interpretATR(v, close); });
        addIndRowBB(indVolatilityEl, 'BB Upper', indicators.bb_upper);
        addIndRowBB(indVolatilityEl, 'BB Lower', indicators.bb_lower);
        var bbInterp = interpretBB(close, indicators.bb_upper, indicators.bb_lower);
        var row = document.createElement('div');
        row.className = 'indicator-row';
        row.innerHTML = '<span class="indicator-name">Bollinger</span><span class="indicator-value">—</span><span class="indicator-badge indicator-badge-' + bbInterp.strength + '">' + bbInterp.label + '</span>';
        indVolatilityEl.appendChild(row);
      }
      if (indVolumeEl) {
        indVolumeEl.innerHTML = '';
        addIndRow(indVolumeEl, 'OBV', indicators.obv, null);
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
    var body = {
      start: params.start,
      end: params.end,
      lookback_days: params.lookback_days,
      hold_days: params.hold_days,
      step_days: params.step_days,
    };
    if (params.symbols && params.symbols.length > 1) {
      body.symbols = params.symbols;
      if (params.strategy_id) body.strategy_id = params.strategy_id;
    } else {
      body.symbol = params.symbol || params.symbols[0];
      if (params.strategy_id) body.strategy_id = params.strategy_id;
    }
    try {
      const res = await fetchJson(`${API_BASE}/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
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

  async function loadDashboard() {
    const loading = document.getElementById('dashboard-loading');
    const bodyEl = document.getElementById('dashboard-body');
    const lookback = parseInt(document.getElementById('dashboard-lookback') && document.getElementById('dashboard-lookback').value, 10) || 90;
    loading.hidden = false;
    loading.textContent = 'Loading…';
    if (bodyEl) bodyEl.hidden = true;
    await ensureDashboardView();
    buildDashboardHeader(getDashboardColumnsConfig());
    try {
      const lookbackVal = Math.max(20, Math.min(365, lookback));
      const url = `${API_BASE}/dashboard?lookback_days=${lookbackVal}&_t=${Date.now()}`;
      const resp = await fetch(url, { cache: 'no-store' });
      if (!resp.ok) throw new Error(resp.statusText || 'Request failed');
      const text = await resp.text();
      let res = {};
      try {
        res = JSON.parse(text);
      } catch (e) {
        console.error('Dashboard JSON parse failed', e);
        throw new Error('Invalid JSON from server');
      }
      if (typeof res === 'string') {
        try { res = JSON.parse(res); } catch (e2) { res = {}; }
      }
      const stocks = Array.isArray(res.stocks) ? res.stocks : [];
      console.log('Dashboard response: count=', res.count, 'stocks.length=', stocks.length, 'first=', stocks[0]);
      const summaryEl = document.getElementById('dashboard-summary');
      if (summaryEl) {
        var msg = stocks.length + ' stock(s). Click Refresh to update.';
        if (res.error) msg = res.error + ' — ' + msg;
        summaryEl.textContent = msg;
      }
      const tbody = document.getElementById('dashboard-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        var cols = getDashboardColumnsConfig();
        var visible = cols.filter(function (c) { return c.visible; }).sort(function (a, b) { return a.order - b.order; });
        stocks.forEach(function (row) {
          try {
            const tr = document.createElement('tr');
            const name = (row.company_name || row.symbol || '—').trim() || row.symbol || '—';
            const ind = row.indicators && typeof row.indicators === 'object' ? row.indicators : {};
            function fmt(val, decimals) {
              if (val == null || Number.isNaN(Number(val))) return '—';
              return formatNum(Number(val), decimals);
            }
            const sig = (row.signal && row.signal.action) ? row.signal.action : 'HOLD';
            const reason = (row.signal && row.signal.reason) ? row.signal.reason : '—';
            const sigClass = 'signal-badge signal-badge-' + (sig || 'hold').toLowerCase();
            visible.forEach(function (col) {
              var td = document.createElement('td');
              if (col.key === 'stock') {
                td.innerHTML = '<span class="dashboard-stock-name">' + escapeHtml(String(name)) + '</span><span class="dashboard-stock-symbol">' + escapeHtml(String(row.symbol || '')) + '</span>';
              } else if (col.key === 'close') { td.className = 'num'; td.textContent = fmt(ind.close, 2);
              } else if (col.key === 'sma_20') { td.className = 'num'; td.textContent = fmt(ind.sma_20, 2);
              } else if (col.key === 'sma_50') { td.className = 'num'; td.textContent = fmt(ind.sma_50, 2);
              } else if (col.key === 'sma_200') { td.className = 'num'; td.textContent = fmt(ind.sma_200, 2);
              } else if (col.key === 'rsi') { td.className = 'num'; td.textContent = fmt(ind.rsi, 1);
              } else if (col.key === 'macd_hist') { td.className = 'num'; td.textContent = fmt(ind.macd_hist, 3);
              } else if (col.key === 'atr') { td.className = 'num'; td.textContent = fmt(ind.atr, 2);
              } else if (col.key === 'signal') { td.innerHTML = '<span class="' + sigClass + '">' + escapeHtml(sig) + '</span>';
              } else if (col.key === 'reason') { td.className = 'dashboard-reason'; td.textContent = reason;
              } else { td.textContent = fmt(ind[col.key], 2);
              }
              tr.appendChild(td);
            });
            var baseSymbol = (row.symbol || '').split('.')[0].trim().toUpperCase() || (row.symbol || '');
            var tdActions = document.createElement('td');
            tdActions.className = 'dashboard-actions-col';
            tdActions.innerHTML = '<button type="button" class="btn btn-secondary btn-sm btn-edit-stock" data-symbol="' + escapeHtml(baseSymbol) + '" title="Edit symbol, Yahoo symbol, or company name">Edit</button> <button type="button" class="btn btn-secondary btn-sm btn-remove-stock" data-symbol="' + escapeHtml(baseSymbol) + '" title="Remove from universe (removes from dashboard and symbol dropdown)">Remove</button>';
            tr.appendChild(tdActions);
            tbody.appendChild(tr);
          } catch (rowErr) {
            console.warn('Dashboard row render error', row, rowErr);
          }
        });
      }
      loading.hidden = true;
      if (bodyEl) {
        bodyEl.hidden = false;
      }
    } catch (e) {
      console.error('Dashboard load error', e);
      if (loading) {
        loading.textContent = 'Error: ' + (e.message || String(e));
        loading.hidden = false;
      }
      if (bodyEl) {
        bodyEl.hidden = false;
      }
      const summaryEl = document.getElementById('dashboard-summary');
      if (summaryEl) summaryEl.textContent = 'Load failed. See message above.';
      const tbody = document.getElementById('dashboard-tbody');
      if (tbody) tbody.innerHTML = '';
    }
  }

  function escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function openDashboardColumnsModal() {
    var modal = document.getElementById('dashboard-columns-modal');
    var listEl = document.getElementById('dashboard-columns-list');
    if (!modal || !listEl) return;
    var cols = getDashboardColumnsConfig();
    listEl.innerHTML = '';
    DASHBOARD_AVAILABLE_COLUMNS.filter(function (c) { return !c.alwaysShow; }).forEach(function (av, idx) {
      var entry = cols.find(function (x) { return x.key === av.key; });
      var visible = entry ? entry.visible : (av.key === 'close' || av.key === 'sma_20' || av.key === 'sma_50' || av.key === 'rsi' || av.key === 'macd_hist' || av.key === 'signal' || av.key === 'reason');
      var order = entry ? entry.order : idx;
      var div = document.createElement('div');
      div.className = 'column-picker-row';
      div.innerHTML = '<label class="checkbox-label"><input type="checkbox" data-key="' + escapeHtml(av.key) + '" ' + (visible ? 'checked' : '') + '> ' + escapeHtml(av.label) + '</label>';
      listEl.appendChild(div);
    });
    modal.hidden = false;
  }
  function closeDashboardColumnsModal() {
    var modal = document.getElementById('dashboard-columns-modal');
    if (modal) modal.hidden = true;
  }
  async function saveDashboardColumnsFromModal() {
    var listEl = document.getElementById('dashboard-columns-list');
    if (!listEl) return;
    var checkboxes = listEl.querySelectorAll('input[type="checkbox"]');
    var visibleKeys = [];
    checkboxes.forEach(function (cb) {
      if (cb.checked) visibleKeys.push(cb.getAttribute('data-key'));
    });
    var current = getDashboardColumnsConfig();
    var keyToOrder = {};
    current.forEach(function (c) { keyToOrder[c.key] = c.order; });
    var order = 0;
    var newConfig = [{ key: 'stock', visible: true, order: 0 }];
    order = 1;
    DASHBOARD_AVAILABLE_COLUMNS.forEach(function (av) {
      if (av.key === 'stock') return;
      var visible = visibleKeys.indexOf(av.key) !== -1;
      newConfig.push({ key: av.key, visible: visible, order: keyToOrder[av.key] != null ? keyToOrder[av.key] : order });
      if (visible) order++;
    });
    newConfig.sort(function (a, b) { return a.order - b.order; });
    dashboardColumnsConfig = newConfig;
    if (dashboardViewId) {
      try {
        await fetchJson(API_BASE + '/api/dashboard/views/' + dashboardViewId, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ columns_config: newConfig }),
        });
      } catch (e) {
        console.warn('Failed to save dashboard view', e);
      }
    }
    closeDashboardColumnsModal();
    buildDashboardHeader(getDashboardColumnsConfig());
    loadDashboard();
  }
  setupTabs();

  var btnRunAnalysis = document.getElementById('btn-run-analysis');
  if (btnRunAnalysis) btnRunAnalysis.addEventListener('click', runAnalysis);
  var btnRunBacktest = document.getElementById('btn-run-backtest');
  if (btnRunBacktest) btnRunBacktest.addEventListener('click', runBacktest);

  // --- Analysis symbol: searchable dropdown (all stocks from universe) ---
  var analysisUniverseSymbols = null;
  var analysisSymbolListOpen = false;
  var analysisSymbolHighlightIndex = -1;

  async function loadAnalysisUniverse() {
    if (analysisUniverseSymbols) return analysisUniverseSymbols;
    try {
      var res = await fetchJson(API_BASE + '/api/data/universe');
      var list = (res && res.symbols) ? res.symbols : [];
      analysisUniverseSymbols = list.map(function (s) {
        return {
          symbol: (s.symbol || s.yahoo_symbol || '').trim(),
          name: (s.company_name || '').trim(),
        };
      }).filter(function (s) { return s.symbol; });
    } catch (e) {
      console.warn('Failed to load universe for analysis symbol dropdown', e);
      analysisUniverseSymbols = [];
    }
    return analysisUniverseSymbols;
  }

  function filterAnalysisSymbols(query) {
    if (!analysisUniverseSymbols) return [];
    var q = (query || '').trim().toLowerCase();
    if (!q) return analysisUniverseSymbols.slice(0, 150);
    return analysisUniverseSymbols.filter(function (s) {
      return s.symbol.toLowerCase().indexOf(q) >= 0 || (s.name && s.name.toLowerCase().indexOf(q) >= 0);
    }).slice(0, 150);
  }

  function renderAnalysisSymbolList(filterQuery) {
    var listbox = document.getElementById('analysis-symbol-listbox');
    var input = document.getElementById('analysis-symbol-input');
    if (!listbox || !input) return;
    var filtered = filterAnalysisSymbols(filterQuery != null ? filterQuery : input.value);
    listbox.innerHTML = '';
    if (filtered.length === 0) {
      var li = document.createElement('li');
      li.className = 'combobox-option-no-match';
      li.setAttribute('role', 'option');
      li.textContent = 'No matching stocks';
      listbox.appendChild(li);
    } else {
      filtered.forEach(function (s, i) {
        var li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.setAttribute('data-symbol', s.symbol);
        li.setAttribute('data-index', String(i));
        var symSpan = document.createElement('span');
        symSpan.className = 'combobox-option-symbol';
        symSpan.textContent = s.symbol;
        li.appendChild(symSpan);
        if (s.name) {
          var nameSpan = document.createElement('span');
          nameSpan.className = 'combobox-option-name';
          nameSpan.textContent = s.name;
          li.appendChild(nameSpan);
        }
        li.addEventListener('click', function () {
          var sym = this.getAttribute('data-symbol');
          if (sym) {
            input.value = sym;
            input.setAttribute('aria-expanded', 'false');
            listbox.hidden = true;
            analysisSymbolListOpen = false;
            analysisSymbolHighlightIndex = -1;
          }
        });
        listbox.appendChild(li);
      });
    }
    listbox.hidden = false;
    analysisSymbolListOpen = true;
    analysisSymbolHighlightIndex = -1;
    input.setAttribute('aria-expanded', 'true');
  }

  function closeAnalysisSymbolList() {
    var listbox = document.getElementById('analysis-symbol-listbox');
    var input = document.getElementById('analysis-symbol-input');
    if (listbox) listbox.hidden = true;
    if (input) input.setAttribute('aria-expanded', 'false');
    analysisSymbolListOpen = false;
    analysisSymbolHighlightIndex = -1;
  }

  function setupAnalysisSymbolCombobox() {
    var input = document.getElementById('analysis-symbol-input');
    var listbox = document.getElementById('analysis-symbol-listbox');
    var trigger = document.getElementById('analysis-symbol-trigger');
    if (!input || !listbox) return;

    function openList() {
      loadAnalysisUniverse().then(function () {
        renderAnalysisSymbolList(input.value);
      });
    }

    input.addEventListener('focus', openList);
    input.addEventListener('input', function () {
      loadAnalysisUniverse().then(function () {
        renderAnalysisSymbolList(input.value);
      });
    });

    if (trigger) {
      trigger.addEventListener('click', function () {
        if (analysisSymbolListOpen) closeAnalysisSymbolList();
        else {
          input.focus();
          openList();
        }
      });
    }

    input.addEventListener('keydown', function (ev) {
      if (!analysisSymbolListOpen) {
        if (ev.key === 'ArrowDown' || ev.key === 'Escape') openList();
        return;
      }
      var options = listbox.querySelectorAll('li[data-symbol]');
      if (ev.key === 'Escape') {
        closeAnalysisSymbolList();
        ev.preventDefault();
        return;
      }
      if (ev.key === 'ArrowDown') {
        analysisSymbolHighlightIndex = Math.min(analysisSymbolHighlightIndex + 1, options.length - 1);
        ev.preventDefault();
      } else if (ev.key === 'ArrowUp') {
        analysisSymbolHighlightIndex = Math.max(analysisSymbolHighlightIndex - 1, -1);
        ev.preventDefault();
      } else if (ev.key === 'Enter' && options.length && analysisSymbolHighlightIndex >= 0 && options[analysisSymbolHighlightIndex]) {
        var sym = options[analysisSymbolHighlightIndex].getAttribute('data-symbol');
        if (sym) {
          input.value = sym;
          closeAnalysisSymbolList();
        }
        ev.preventDefault();
        return;
      }
      options.forEach(function (opt, i) {
        opt.classList.toggle('combobox-option-active', i === analysisSymbolHighlightIndex);
      });
    });

    document.addEventListener('click', function (ev) {
      if (!analysisSymbolListOpen) return;
      if (input.contains(ev.target) || (listbox && listbox.contains(ev.target)) || (trigger && trigger.contains(ev.target))) return;
      closeAnalysisSymbolList();
    });
  }

  setupAnalysisSymbolCombobox();

  var paperSelectedPortfolioId = null;

  async function loadStrategiesTab() {
    var loading = document.getElementById('strategies-loading');
    var body = document.getElementById('strategies-body');
    var listEl = document.getElementById('strategies-list');
    var summaryEl = document.getElementById('strategies-summary');
    if (!listEl) return;
    if (loading) { loading.hidden = false; loading.textContent = 'Loading…'; }
    try {
      var res = await fetchJson(API_BASE + '/api/strategies');
      var strategies = (res && res.strategies) ? res.strategies : [];
      if (summaryEl) summaryEl.textContent = strategies.length + ' strategy(ies).';
      listEl.innerHTML = '';
      strategies.forEach(function (s) {
        var card = document.createElement('div');
        card.className = 'strategy-card';
        var paramsStr = (s.params && typeof s.params === 'object') ? JSON.stringify(s.params, null, 2) : (s.params || '{}');
        var defaultBadge = s.is_global_default ? '<span class="strategy-badge strategy-badge-default">Default</span>' : '';
        card.innerHTML =
          '<div class="strategy-card-header">' +
            '<span class="strategy-name">' + escapeHtml(s.name || s.id) + '</span> ' + defaultBadge +
          '</div>' +
          (s.description ? '<p class="strategy-desc">' + escapeHtml(s.description) + '</p>' : '') +
          '<p class="strategy-meta">Type: ' + escapeHtml(s.strategy_type || 'rule_based') + '</p>' +
          '<pre class="strategy-params">' + escapeHtml(paramsStr) + '</pre>' +
          '<div class="strategy-actions">' +
            (s.is_global_default ? '' : '<button type="button" class="btn btn-secondary btn-sm btn-strategy-set-default" data-strategy-id="' + escapeHtml(s.id) + '">Set as default</button> ') +
            '<button type="button" class="btn btn-secondary btn-sm btn-strategy-delete" data-strategy-id="' + escapeHtml(s.id) + '" data-strategy-name="' + escapeHtml(s.name || s.id) + '">Remove</button>' +
          '</div>';
        listEl.appendChild(card);
      });
    } catch (e) {
      if (summaryEl) summaryEl.textContent = 'Failed to load strategies.';
      console.warn('Strategies load failed', e);
    }
    if (loading) loading.hidden = true;
  }
  var strategiesListEl = document.getElementById('strategies-list');
  if (strategiesListEl) {
    strategiesListEl.addEventListener('click', function (ev) {
      var target = ev.target;
      if (target.classList && target.classList.contains('btn-strategy-delete')) {
        ev.preventDefault();
        var id = target.getAttribute('data-strategy-id');
        var name = target.getAttribute('data-strategy-name') || id;
        if (!id) return;
        if (!confirm("Remove strategy \"" + name + "\"? This cannot be undone.")) return;
        fetch(API_BASE + '/api/strategies/' + encodeURIComponent(id), { method: 'DELETE' })
          .then(function (r) {
            if (r.ok) loadStrategiesTab();
            else r.text().then(function (t) { console.warn('Delete failed', t); });
          })
          .catch(function (e) { console.warn('Delete failed', e); });
      }
      if (target.classList && target.classList.contains('btn-strategy-set-default')) {
        ev.preventDefault();
        var id = target.getAttribute('data-strategy-id');
        if (!id) return;
        fetch(API_BASE + '/api/strategies/' + encodeURIComponent(id) + '/set-default', { method: 'POST' })
          .then(function (r) {
            if (r.ok) loadStrategiesTab();
            else r.text().then(function (t) { console.warn('Set default failed', t); });
          })
          .catch(function (e) { console.warn('Set default failed', e); });
      }
    });
  }
  var btnStrategiesAdd = document.getElementById('btn-strategies-add');
  if (btnStrategiesAdd) {
    btnStrategiesAdd.addEventListener('click', function (ev) {
      ev.preventDefault();
      var modal = document.getElementById('add-strategy-modal');
      if (!modal) return;
      var nameEl = document.getElementById('add-strategy-name');
      var descEl = document.getElementById('add-strategy-desc');
      var paramsEl = document.getElementById('add-strategy-params');
      var defaultEl = document.getElementById('add-strategy-default');
      if (nameEl) nameEl.value = '';
      if (descEl) descEl.value = '';
      if (paramsEl) paramsEl.value = '{"rsi_buy_below": 30, "rsi_sell_above": 70}';
      if (defaultEl) defaultEl.checked = false;
      modal.hidden = false;
    });
  }
  var btnAddStrategySubmit = document.getElementById('btn-add-strategy-submit');
  if (btnAddStrategySubmit) {
    btnAddStrategySubmit.addEventListener('click', async function (ev) {
      ev.preventDefault();
      var nameEl = document.getElementById('add-strategy-name');
      var name = (nameEl && nameEl.value && nameEl.value.trim()) || '';
      if (!name) { alert('Name is required.'); return; }
      var descEl = document.getElementById('add-strategy-desc');
      var desc = (descEl && descEl.value) ? descEl.value.trim() : '';
      var typeEl = document.getElementById('add-strategy-type');
      var strategyType = (typeEl && typeEl.value) ? typeEl.value : 'rule_based';
      var paramsEl = document.getElementById('add-strategy-params');
      var paramsStr = (paramsEl && paramsEl.value) ? paramsEl.value.trim() : '{}';
      var params = {};
      try {
        if (paramsStr) params = JSON.parse(paramsStr);
      } catch (e) {
        alert('Params must be valid JSON.');
        return;
      }
      var defaultEl = document.getElementById('add-strategy-default');
      var isDefault = defaultEl ? defaultEl.checked : false;
      try {
        await fetchJson(API_BASE + '/api/strategies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, description: desc, strategy_type: strategyType, params: params, is_global_default: isDefault }),
        });
        var modal = document.getElementById('add-strategy-modal');
        if (modal) modal.hidden = true;
        loadStrategiesTab();
        loadBacktestStrategies();
      } catch (e) {
        console.warn('Add strategy failed', e);
        alert('Failed to add strategy.');
      }
    });
  }
  var btnAddStrategyCancel = document.getElementById('btn-add-strategy-cancel');
  if (btnAddStrategyCancel) {
    btnAddStrategyCancel.addEventListener('click', function (ev) {
      ev.preventDefault();
      var m = document.getElementById('add-strategy-modal');
      if (m) m.hidden = true;
    });
  }

  var btnAddStock = document.getElementById('btn-add-stock');
  if (btnAddStock) {
    btnAddStock.addEventListener('click', function (ev) {
      ev.preventDefault();
      var modal = document.getElementById('add-stock-modal');
      if (!modal) return;
      var symEl = document.getElementById('add-stock-symbol');
      var companyEl = document.getElementById('add-stock-company');
      if (symEl) symEl.value = '';
      if (companyEl) companyEl.value = '';
      modal.hidden = false;
    });
  }
  var btnAddStockSubmit = document.getElementById('btn-add-stock-submit');
  if (btnAddStockSubmit) {
    btnAddStockSubmit.addEventListener('click', async function (ev) {
      ev.preventDefault();
      var symEl = document.getElementById('add-stock-symbol');
      var symbol = (symEl && symEl.value && symEl.value.trim()) || '';
      if (!symbol) {
        alert('Enter a symbol (e.g. TCS, INFY).');
        return;
      }
      var companyEl = document.getElementById('add-stock-company');
      var companyName = (companyEl && companyEl.value) ? companyEl.value.trim() : '';
      btnAddStockSubmit.disabled = true;
      btnAddStockSubmit.textContent = 'Fetching 10 years…';
      try {
        var res = await fetchJson(API_BASE + '/api/data/universe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol: symbol,
            company_name: companyName || undefined,
            lookback_days: 3650
          }),
        });
        var modal = document.getElementById('add-stock-modal');
        if (modal) modal.hidden = true;
        analysisUniverseSymbols = null;
        var addedSym = (res && res.symbol) ? res.symbol : symbol;
        var analysisInput = document.getElementById('analysis-symbol-input');
        if (analysisInput) analysisInput.value = addedSym;
        if (typeof loadDashboard === 'function') loadDashboard();
        if (typeof loadAnalysisUniverse === 'function') loadAnalysisUniverse().then(function () { if (typeof renderAnalysisSymbolList === 'function') renderAnalysisSymbolList(addedSym); });
        if (res.fetched) {
          var msg = 'Added "' + addedSym + '" and fetched data (' + (res.lookback_days || 3650) + ' days).';
          if (res.error_message) msg += ' ' + res.error_message;
          msg += ' It will appear in Dashboard, Analysis, Backtest and Paper.';
          alert(msg);
        } else {
          alert('Added "' + addedSym + '" but data fetch failed. ' + (res.error_message || 'Try Data seed or run analysis for this symbol.'));
        }
      } catch (e) {
        console.warn('Add stock failed', e);
        alert('Failed to add stock: ' + (e.message || String(e)));
      }
      btnAddStockSubmit.disabled = false;
      btnAddStockSubmit.textContent = 'Add and fetch data';
    });
  }
  var btnAddStockCancel = document.getElementById('btn-add-stock-cancel');
  if (btnAddStockCancel) {
    btnAddStockCancel.addEventListener('click', function (ev) {
      ev.preventDefault();
      var m = document.getElementById('add-stock-modal');
      if (m) m.hidden = true;
    });
  }

  async function loadPaperPortfolios() {
    try {
      var res = await fetchJson(API_BASE + '/api/paper/portfolios');
      var list = (res && res.portfolios) ? res.portfolios : [];
      var ul = document.getElementById('paper-portfolios-list');
      if (!ul) return;
      ul.innerHTML = '';
      list.forEach(function (p) {
        var li = document.createElement('li');
        li.innerHTML = '<a href="#" data-portfolio-id="' + escapeHtml(p.id) + '">' + escapeHtml(p.name) + '</a> (' + formatNum(p.initial_capital, 0) + ' ' + (p.currency || 'INR') + ')';
        li.querySelector('a').addEventListener('click', function (e) { e.preventDefault(); selectPaperPortfolio(p.id); });
        ul.appendChild(li);
      });
    } catch (e) {
      console.warn('Paper portfolios load failed', e);
    }
  }
  async function selectPaperPortfolio(id) {
    paperSelectedPortfolioId = id;
    var wrap = document.getElementById('paper-detail-wrap');
    if (wrap) wrap.hidden = false;
    try {
      var res = await fetchJson(API_BASE + '/api/paper/portfolios/' + id);
      var p = res.portfolio;
      var positions = res.positions || [];
      document.getElementById('paper-detail-title').textContent = p.name;
      document.getElementById('paper-detail-meta').textContent = 'Initial: ' + formatNum(p.initial_capital, 0) + ' ' + (p.currency || 'INR');
      var tbody = document.getElementById('paper-positions-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        positions.forEach(function (pos) {
          var tr = document.createElement('tr');
          tr.innerHTML = '<td>' + escapeHtml(pos.symbol) + '</td><td>' + (pos.strategy_ids && pos.strategy_ids.length ? pos.strategy_ids.join(', ') : 'Default') + '</td><td><button type="button" class="btn-remove" data-symbol="' + escapeHtml(pos.symbol) + '">Remove</button></td>';
          tbody.appendChild(tr);
        });
      }
      var snapRes = await fetchJson(API_BASE + '/api/paper/portfolios/' + id + '/snapshots');
      var snaps = (snapRes && snapRes.snapshots) ? snapRes.snapshots : [];
      var snapEl = document.getElementById('paper-snapshots');
      if (snapEl) {
        if (snaps.length) {
          var last = snaps[snaps.length - 1];
          snapEl.textContent = 'Last snapshot: ' + last.date + ' — Equity: ' + formatNum(last.equity, 2) + ', Cash: ' + formatNum(last.cash, 2);
        } else {
          snapEl.textContent = 'No snapshots yet. Add positions and click Run simulation.';
        }
      }
    } catch (e) {
      console.warn('Paper portfolio detail failed', e);
    }
  }
  var btnPaperNew = document.getElementById('btn-paper-new-portfolio');
  if (btnPaperNew) {
    btnPaperNew.addEventListener('click', async function () {
      var name = prompt('Portfolio name', 'My Paper Portfolio');
      if (!name) return;
      var cap = parseFloat(prompt('Initial capital', '1000000'), 10) || 1000000;
      try {
        await fetchJson(API_BASE + '/api/paper/portfolios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name, initial_capital: cap, currency: 'INR' }) });
        loadPaperPortfolios();
      } catch (e) {
        console.warn('Create portfolio failed', e);
      }
    });
  }
  var btnPaperAddPosition = document.getElementById('btn-paper-add-position');
  if (btnPaperAddPosition) {
    btnPaperAddPosition.addEventListener('click', async function () {
      if (!paperSelectedPortfolioId) return;
      var sym = (document.getElementById('paper-add-symbol') && document.getElementById('paper-add-symbol').value) || '';
      if (!sym.trim()) return;
      try {
        await fetchJson(API_BASE + '/api/paper/portfolios/' + paperSelectedPortfolioId + '/positions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: sym.trim(), strategy_ids: [] }) });
        selectPaperPortfolio(paperSelectedPortfolioId);
      } catch (e) {
        console.warn('Add position failed', e);
      }
    });
  }
  var paperDetailWrap = document.getElementById('paper-detail-wrap');
  if (paperDetailWrap) {
    paperDetailWrap.addEventListener('click', async function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('btn-remove') && e.target.getAttribute('data-symbol') && paperSelectedPortfolioId) {
      var sym = e.target.getAttribute('data-symbol');
      try {
        await fetchJson(API_BASE + '/api/paper/portfolios/' + paperSelectedPortfolioId + '/positions/' + encodeURIComponent(sym), { method: 'DELETE' });
        selectPaperPortfolio(paperSelectedPortfolioId);
      } catch (err) {
        console.warn('Remove position failed', err);
      }
    }
    });
  }
  var btnPaperRun = document.getElementById('btn-paper-run');
  if (btnPaperRun) {
    btnPaperRun.addEventListener('click', async function () {
      if (!paperSelectedPortfolioId) return;
      try {
        var res = await fetchJson(API_BASE + '/api/paper/portfolios/' + paperSelectedPortfolioId + '/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
        if (res && res.ok) selectPaperPortfolio(paperSelectedPortfolioId);
      } catch (e) {
        console.warn('Run simulation failed', e);
      }
    });
  }
  var btnSaveStrategy = document.getElementById('btn-save-strategy');
  if (btnSaveStrategy) {
    btnSaveStrategy.addEventListener('click', function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var modal = document.getElementById('save-strategy-modal');
      if (modal) { document.getElementById('save-strategy-name').value = ''; document.getElementById('save-strategy-desc').value = ''; modal.hidden = false; }
    });
  }
  var btnSaveStrategySubmit = document.getElementById('btn-save-strategy-submit');
  if (btnSaveStrategySubmit) {
    btnSaveStrategySubmit.addEventListener('click', async function () {
      var name = (document.getElementById('save-strategy-name') && document.getElementById('save-strategy-name').value) || 'My strategy';
      var desc = (document.getElementById('save-strategy-desc') && document.getElementById('save-strategy-desc').value) || '';
      try {
        await fetchJson(API_BASE + '/api/strategies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, description: desc, strategy_type: 'rule_based', params: { rsi_buy_below: 30, rsi_sell_above: 70 } }),
        });
        var modal = document.getElementById('save-strategy-modal');
        if (modal) modal.hidden = true;
        loadBacktestStrategies();
      } catch (e) {
        console.warn('Save strategy failed', e);
      }
    });
  }
  var btnSaveStrategyCancel = document.getElementById('btn-save-strategy-cancel');
  if (btnSaveStrategyCancel) btnSaveStrategyCancel.addEventListener('click', function () { var m = document.getElementById('save-strategy-modal'); if (m) m.hidden = true; });
  var btnDashboardRefresh = document.getElementById('btn-dashboard-refresh');
  if (btnDashboardRefresh) btnDashboardRefresh.addEventListener('click', loadDashboard);
  var tableDashboard = document.getElementById('table-dashboard');
  if (tableDashboard) {
    tableDashboard.addEventListener('click', async function (ev) {
      if (ev.target && ev.target.classList && ev.target.classList.contains('btn-edit-stock')) {
        var sym = ev.target.getAttribute('data-symbol');
        if (!sym) return;
        var modal = document.getElementById('edit-stock-modal');
        if (!modal) return;
        try {
          var data = await fetchJson(API_BASE + '/api/data/universe/item/' + encodeURIComponent(sym));
          modal.setAttribute('data-current-symbol', sym);
          var symInput = document.getElementById('edit-stock-symbol');
          var yahooInput = document.getElementById('edit-stock-yahoo');
          var companyInput = document.getElementById('edit-stock-company');
          if (symInput) symInput.value = data.symbol || sym;
          if (yahooInput) yahooInput.value = data.yahoo_symbol || '';
          if (companyInput) companyInput.value = data.company_name || '';
          modal.hidden = false;
        } catch (e) {
          console.warn('Load symbol for edit failed', e);
          alert('Failed to load symbol: ' + (e.message || String(e)));
        }
      }
      if (ev.target && ev.target.classList && ev.target.classList.contains('btn-remove-stock')) {
        var sym = ev.target.getAttribute('data-symbol');
        if (!sym) return;
        if (!confirm('Remove "' + sym + '" from universe? It will disappear from the dashboard and symbol dropdown.')) return;
        try {
          await fetchJson(API_BASE + '/api/data/universe/' + encodeURIComponent(sym), { method: 'DELETE' });
          analysisUniverseSymbols = null;
          loadDashboard();
        } catch (e) {
          console.warn('Remove stock failed', e);
          alert('Failed to remove: ' + (e.message || String(e)));
        }
      }
    });
  }
  var btnEditStockSave = document.getElementById('btn-edit-stock-save');
  if (btnEditStockSave) {
    btnEditStockSave.addEventListener('click', async function () {
      var modal = document.getElementById('edit-stock-modal');
      var currentSym = modal ? modal.getAttribute('data-current-symbol') : null;
      if (!currentSym) return;
      var symInput = document.getElementById('edit-stock-symbol');
      var yahooInput = document.getElementById('edit-stock-yahoo');
      var companyInput = document.getElementById('edit-stock-company');
      var newSymbol = symInput && symInput.value ? symInput.value.trim().toUpperCase() : currentSym;
      if (!newSymbol) {
        alert('Symbol is required.');
        return;
      }
      var body = { symbol: newSymbol };
      if (yahooInput && yahooInput.value.trim()) body.yahoo_symbol = yahooInput.value.trim();
      if (companyInput) body.company_name = companyInput.value.trim();
      var btn = this;
      btn.disabled = true;
      btn.textContent = 'Saving…';
      try {
        var res = await fetchJson(API_BASE + '/api/data/universe/' + encodeURIComponent(currentSym), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (modal) modal.hidden = true;
        analysisUniverseSymbols = null;
        loadDashboard();
        if (res.error_message) alert(res.error_message);
      } catch (e) {
        console.warn('Edit stock failed', e);
        alert('Failed to save: ' + (e.message || String(e)));
      } finally {
        btn.disabled = false;
        btn.textContent = 'Save';
      }
    });
  }
  var btnEditStockCancel = document.getElementById('btn-edit-stock-cancel');
  if (btnEditStockCancel) btnEditStockCancel.addEventListener('click', function () {
    var m = document.getElementById('edit-stock-modal');
    if (m) m.hidden = true;
  });
  var btnDashboardColumns = document.getElementById('btn-dashboard-columns');
  if (btnDashboardColumns) btnDashboardColumns.addEventListener('click', function (ev) {
    ev.preventDefault();
    ev.stopPropagation();
    openDashboardColumnsModal();
  });
  var btnDashboardColumnsSave = document.getElementById('btn-dashboard-columns-save');
  if (btnDashboardColumnsSave) btnDashboardColumnsSave.addEventListener('click', saveDashboardColumnsFromModal);
  var btnDashboardColumnsCancel = document.getElementById('btn-dashboard-columns-cancel');
  if (btnDashboardColumnsCancel) btnDashboardColumnsCancel.addEventListener('click', function (ev) { ev.preventDefault(); closeDashboardColumnsModal(); });
})();
