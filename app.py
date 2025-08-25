from flask import Flask, render_template_string, request
import yfinance as yf
from groq import Groq
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd
from datetime import datetime
import re  # Added for markdown rendering

app = Flask(__name__)

# List of AI-related stock tickers
AI_TICKERS = ['NVDA', 'GOOGL', 'MSFT', 'AMD', 'INTC', 'TSLA', 'AAPL', 'AMZN']

def basic_markdown(text):
    """Simple function to convert Markdown to HTML, similar to the CRM app."""
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'^\s*#\s+(.*)$', r'<h1>\1</h1>', text, flags=re.M)
    text = re.sub(r'^\s*##\s+(.*)$', r'<h2>\1</h2>', text, flags=re.M)
    text = re.sub(r'^\s*###\s+(.*)$', r'<h3>\1</h3>', text, flags=re.M)
    text = re.sub(r'^\s*-\s+(.*)$', r'<li>\1</li>', text, flags=re.M)
    text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text, flags=re.S)
    text = text.replace('\n', '<br>')
    return text

# Updated HTML template with UI inspired by the CRM's AI Insight page
HTML_TEMPLATE = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AI Stock Market Prediction Tool</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons/font/bootstrap-icons.css" rel="stylesheet">
    <style>
      body { background-color: #f8f9fa; }
      .card { border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
      .insight-card { background-color: #f8f9fa; border-radius: 10px; padding: 20px; }
      .insight-card h2 { color: #007bff; }
      .customer-details { font-size: 0.9em; color: #6c757d; }
      .prediction-card { background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); border: 1px solid #e0e0e0; border-radius: 15px; padding: 20px; margin-top: 20px; box-shadow: 0 8px 20px rgba(0,0,0,0.1); transition: all 0.4s ease; }
      .prediction-card:hover { box-shadow: 0 12px 30px rgba(0,0,0,0.15); transform: translateY(-4px); }
      .btn:hover { transform: translateY(-5px) scale(1.05); box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
      .list-group-item { border: none; }
      .img-fluid { border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    </style>
  </head>
  <body>
    <div class="container my-5">
      <h1 class="text-center mb-4"><i class="bi bi-graph-up-arrow me-2"></i>AI Stock Market Prediction</h1>
      <p class="text-center text-muted">Select an AI-related stock, provide your Groq API key, and get market details with a prediction. Note: This is for educational purposes only and not financial advice.</p>
      
      <form method="POST" class="card p-4 shadow mb-5">
        <div class="mb-3">
          <label for="ticker" class="form-label">Select Stock Ticker</label>
          <select class="form-select" id="ticker" name="ticker" required>
            <option value="" disabled selected>Select a ticker</option>
            {% for t in ai_tickers %}
              <option value="{{ t }}">{{ t }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="mb-3">
          <label for="api_key" class="form-label">Groq API Key</label>
          <input type="text" class="form-control" id="api_key" name="api_key" required placeholder="Enter your Groq API key">
          <div class="form-text">Obtain your API key from <a href="https://console.groq.com/keys" target="_blank">Groq Console</a>. It is not stored.</div>
        </div>
        <button type="submit" class="btn btn-primary w-100">Get Prediction</button>
      </form>
      
      {% if error %}
        <div class="alert alert-danger mt-4">{{ error }}</div>
      {% endif %}
      
      {% if results %}
        <h1 class="mb-4 text-center"><i class="bi bi-lightbulb-fill me-2"></i>AI-Powered Prediction for {{ results.ticker }}</h1>
        
        <div class="card insight-card mb-4">
          <div class="card-header bg-primary text-white">
            <h4 class="mb-0">Market Overview</h4>
          </div>
          <div class="card-body">
            <ul class="list-group list-group-flush">
              <li class="list-group-item"><strong>Current Price:</strong> {{ results.current_price|floatformat(2) }}</li>
              <li class="list-group-item"><strong>52-Week High:</strong> {{ results.high_52w|floatformat(2) }}</li>
              <li class="list-group-item"><strong>52-Week Low:</strong> {{ results.low_52w|floatformat(2) }}</li>
              <li class="list-group-item"><strong>Market Cap:</strong> {{ results.market_cap|floatformat(2) }}B</li>
              <li class="list-group-item"><strong>Volume:</strong> {{ results.volume|intcomma }}</li>
            </ul>
          </div>
        </div>
        
        <div class="card insight-card mb-4">
          <div class="card-header bg-info text-white">
            <h4 class="mb-0">Historical Price Chart (1 Year)</h4>
          </div>
          <div class="card-body text-center">
            <img src="data:image/png;base64,{{ results.chart_img }}" class="img-fluid" alt="Stock Chart">
          </div>
        </div>
        
        <div class="card insight-card mb-4">
          <div class="card-header bg-secondary text-white">
            <h4 class="mb-0">Recent News</h4>
          </div>
          <div class="card-body">
            {% if results.news %}
              <ul class="list-group">
                {% for news_item in results.news %}
                  <li class="list-group-item">
                    <a href="{{ news_item.link }}" target="_blank">{{ news_item.title|default("No title available") }}</a>
                    ({{ news_item.publisher|default("Unknown") }})
                  </li>
                {% endfor %}
              </ul>
            {% else %}
              <p class="text-muted">No recent news available.</p>
            {% endif %}
          </div>
        </div>
        
        <div class="card insight-card prediction-card">
          <div class="card-header bg-success text-white">
            <h4 class="mb-0">Generated AI Prediction</h4>
          </div>
          <div class="card-body">
            {{ results.prediction_html | safe }}
          </div>
        </div>
        
        <div class="mt-4 text-center">
          <button type="button" class="btn btn-warning me-2" onclick="history.back()"><i class="bi bi-arrow-repeat"></i> Regenerate</button>
          <a href="/" class="btn btn-secondary"><i class="bi bi-house-door"></i> Back to Home</a>
        </div>
      {% endif %}
    </div>
    <footer class="text-center text-muted py-4">
      <p>Powered by Yahoo Finance and Groq | Last updated: {{ current_time }}</p>
    </footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
'''

# Custom filters for formatting numbers (unchanged)
def floatformat(value, precision=2):
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{float(value):.{precision}f}"
    except (ValueError, TypeError):
        return "N/A"

def intcomma(value):
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "N/A"

app.jinja_env.filters['floatformat'] = floatformat
app.jinja_env.filters['intcomma'] = intcomma

@app.route('/', methods=['GET', 'POST'])
def index():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Default context for rendering
    context = {
        'ai_tickers': AI_TICKERS,
        'current_time': current_time,
        'error': None,
        'results': None
    }

    if request.method == 'POST':
        ticker = request.form.get('ticker')
        api_key = request.form.get('api_key')
        
        if not ticker or not api_key:
            context['error'] = "Please provide both ticker and API key."
            return render_template_string(HTML_TEMPLATE, **context)
        
        try:
            # Validate ticker
            if ticker not in AI_TICKERS:
                raise ValueError("Invalid ticker selected.")
            
            # Fetch stock data from Yahoo Finance
            stock = yf.Ticker(ticker)
            info = stock.info
            history = stock.history(period="1y")
            
            if history.empty:
                raise ValueError("No historical data found for this ticker.")
            
            # Extract stock data with fallbacks
            current_price = info.get('currentPrice', "N/A")
            high_52w = info.get('fiftyTwoWeekHigh', "N/A")
            low_52w = info.get('fiftyTwoWeekLow', "N/A")
            market_cap = info.get('marketCap', 0) / 1e9 if info.get('marketCap') else "N/A"
            volume = info.get('volume', "N/A")
            
            # Fetch news with safe key access
            news_list = stock.news[:5]  # Top 5 news items
            news = [
                {
                    'title': n.get('title', 'No title available'),
                    'publisher': n.get('publisher', 'Unknown'),
                    'link': n.get('link', '#')
                } for n in news_list
            ]
            
            # Generate chart
            plt.figure(figsize=(10, 5))
            plt.plot(history.index, history['Close'], label='Close Price', color='#007bff')
            plt.title(f'{ticker} 1-Year Price History', fontsize=14, pad=10)
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Price ($)', fontsize=12)
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            chart_img = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            # Prepare data summary for Groq prompt
            history_summary = history['Close'].describe().to_string()
            news_summary = "\n".join([f"- {n['title']}" for n in news]) if news else "No recent news available."
            
            # Use Groq API for prediction
            try:
                client = Groq(api_key=api_key)
                prompt = f"""
                You are a stock market analyst. Based on the following data for {ticker}:
                
                Historical price summary (1 year):
                {history_summary}
                
                Recent news:
                {news_summary}
                
                Predict the stock price trend for the next month. Provide a reasoned analysis and a predicted price range.
                Note: This is for educational purposes only and not financial advice.
                Format your response with markdown-style headings (e.g., ## Section Title) and use asterisks (*) for emphasis where needed. Use lists for recommendations or key points.
                Suggested sections: ## Stock Market Analysis, ## Recent News Summary, ## Predicted Stock Price Trend, ## Note
                """
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500
                )
                prediction = completion.choices[0].message.content.strip()
                prediction_html = basic_markdown(prediction)  # Convert to HTML
            except Exception as e:
                prediction_html = f"Failed to generate prediction: {str(e)}"
            
            # Package results
            context['results'] = {
                'ticker': ticker,
                'current_price': current_price,
                'high_52w': high_52w,
                'low_52w': low_52w,
                'market_cap': market_cap,
                'volume': volume,
                'news': news,
                'chart_img': chart_img,
                'prediction_html': prediction_html  # Use rendered HTML
            }
            
            return render_template_string(HTML_TEMPLATE, **context)
        
        except Exception as e:
            context['error'] = f"Error: {str(e)}"
            return render_template_string(HTML_TEMPLATE, **context)
    
    return render_template_string(HTML_TEMPLATE, **context)

if __name__ == '__main__':
    app.run(debug=True)