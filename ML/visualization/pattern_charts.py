"""
Pattern Chart Generator using Plotly
Creates interactive charts for multi-modal trading signals
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("pattern_charts")


class PatternChartGenerator:
    """Generate interactive pattern charts using Plotly"""
    
    def __init__(self, theme='plotly_white'):
        """
        Initialize chart generator
        
        Args:
            theme: Plotly theme ('plotly_white', 'plotly_dark', 'seaborn', etc.)
        """
        self.theme = theme
        logger.info(f"PatternChartGenerator initialized with theme: {theme}")
    
    def create_pattern_chart(self, df: pd.DataFrame, signal, show_volume: bool = True):
        """
        Create interactive chart for a MultiModalSignal
        
        Args:
            df: DataFrame with OHLC data (columns: open, high, low, close, volume)
            signal: MultiModalSignal object
            show_volume: Whether to show volume subplot
            
        Returns:
            HTML string for embedding in template
        """
        try:
            # Ensure df has lowercase columns
            df = df.copy()
            df.columns = df.columns.str.lower()
            
            # Create figure with optional volume subplot
            if show_volume and 'volume' in df.columns:
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    row_heights=[0.7, 0.3],
                    subplot_titles=(f'{signal.ticker} - {signal.pattern_type}', 'Volume')
                )
                has_volume = True
            else:
                fig = go.Figure()
                has_volume = False
            
            # Add candlestick
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name='Price',
                    increasing_line_color='#26a69a',
                    decreasing_line_color='#ef5350',
                    increasing_fillcolor='#26a69a',
                    decreasing_fillcolor='#ef5350'
                ),
                row=1 if has_volume else None,
                col=1 if has_volume else None
            )
            
            # Add volume if available
            if has_volume:
                colors = ['#ef5350' if close < open else '#26a69a' 
                         for close, open in zip(df['close'], df['open'])]
                fig.add_trace(
                    go.Bar(
                        x=df.index,
                        y=df['volume'],
                        name='Volume',
                        marker_color=colors,
                        opacity=0.5,
                        showlegend=False
                    ),
                    row=2, col=1
                )
            
            # Determine if pattern is bullish or bearish
            is_bullish = 'BULLISH' in signal.pattern_type.upper()
            
            # Calculate percentages
            target_pct = ((signal.target_price/signal.entry_price-1)*100)
            sl_pct = ((signal.stop_loss/signal.entry_price-1)*100)
            
            # Add entry line
            direction_label = "LONG" if is_bullish else "SHORT"
            self._add_price_line(
                fig, signal.entry_price, 'blue', 'solid',
                f"Entry ({direction_label}): ₹{signal.entry_price:.2f}",
                row=1 if has_volume else None
            )
            
            # Add target line (green for profit target)
            self._add_price_line(
                fig, signal.target_price, 'green', 'dash',
                f"Target: ₹{signal.target_price:.2f} ({target_pct:+.1f}%)",
                row=1 if has_volume else None
            )
            
            # Add stop loss line (red for loss)
            self._add_price_line(
                fig, signal.stop_loss, 'red', 'dash',
                f"Stop Loss: ₹{signal.stop_loss:.2f} ({sl_pct:+.1f}%)",
                row=1 if has_volume else None
            )
            
            # Add pattern info annotation
            pattern_text = (
                f"<b>{signal.pattern_type}</b><br>"
                f"<b>Recommendation:</b> {signal.recommendation}<br>"
                f"<b>Confidence:</b> {signal.final_confidence:.1%}<br>"
                f"<b>Risk:Reward:</b> {signal.risk_reward_ratio:.2f}:1<br>"
                f"<b>Position Size:</b> {signal.position_size_pct:.2f}%"
            )
            
            fig.add_annotation(
                x=df.index[min(5, len(df)-1)],
                y=df['high'].max() * 1.01,
                text=pattern_text,
                showarrow=True,
                arrowhead=2,
                arrowcolor="#2196F3",
                font=dict(size=11, color="#1976D2"),
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor="#2196F3",
                borderwidth=2,
                borderpad=8,
                row=1 if has_volume else None,
                col=1 if has_volume else None
            )
            
            # Add sentiment indicator
            sentiment_color = "#4CAF50" if signal.sentiment_raw > 0 else "#F44336"
            sentiment_icon = "📈" if signal.sentiment_raw > 0 else "📉"
            
            sentiment_text = (
                f"{sentiment_icon} <b>{signal.sentiment_label}</b><br>"
                f"Score: {signal.sentiment_raw:+.2f}<br>"
                f"Articles: {signal.num_articles}<br>"
                f"Confidence: {signal.sentiment_confidence:.0%}"
            )
            
            fig.add_annotation(
                x=df.index[-min(5, len(df)-1)],
                y=df['low'].min() * 0.99,
                text=sentiment_text,
                showarrow=False,
                font=dict(size=10, color=sentiment_color),
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor=sentiment_color,
                borderwidth=2,
                borderpad=6,
                row=1 if has_volume else None,
                col=1 if has_volume else None
            )
            
            # Add prediction indicator
            pred_color = "#4CAF50" if signal.predicted_return > 0 else "#F44336"
            pred_icon = "↗️" if signal.predicted_return > 0 else "↘️"
            
            pred_text = (
                f"{pred_icon} <b>Forecast</b><br>"
                f"Return: {signal.predicted_return*100:+.1f}%<br>"
                f"Prob. Gain: {signal.probability_gain:.0%}"
            )
            
            fig.add_annotation(
                x=df.index[-min(10, len(df)-1)],
                y=df['high'].max() * 1.01,
                text=pred_text,
                showarrow=False,
                font=dict(size=10, color=pred_color),
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor=pred_color,
                borderwidth=2,
                borderpad=6,
                row=1 if has_volume else None,
                col=1 if has_volume else None
            )
            
            # Determine title color based on recommendation
            title_color = {
                'STRONG_BUY': '#4CAF50',
                'BUY': '#8BC34A',
                'WEAK_BUY': '#FFC107',
                'HOLD': '#9E9E9E'
            }.get(signal.recommendation, '#2196F3')
            
            # Update layout
            fig.update_layout(
                title=dict(
                    text=f"<b>{signal.ticker}</b> ({signal.company_name}) - <span style='color:{title_color}'>{signal.recommendation}</span>",
                    font=dict(size=20),
                    x=0.5,
                    xanchor='center'
                ),
                xaxis_title="Date",
                yaxis_title="Price (₹)",
                template=self.theme,
                height=700 if has_volume else 600,
                showlegend=True,
                hovermode='x unified',
                xaxis_rangeslider_visible=False,
                plot_bgcolor='rgba(250,250,250,1)' if self.theme == 'plotly_white' else None
            )
            
            # Update y-axes
            if has_volume:
                fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
                fig.update_yaxes(title_text="Volume", row=2, col=1)
            
            logger.info(f"Chart created for {signal.ticker}")
            
            return fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d']
                }
            )
        
        except Exception as e:
            logger.error(f"Error creating chart for {signal.ticker}: {e}")
            return f"<div class='alert alert-danger'>Error creating chart: {e}</div>"
    
    def _add_price_line(self, fig, price, color, dash, annotation, row=None):
        """Helper to add horizontal price line"""
        fig.add_hline(
            y=price,
            line_dash=dash,
            line_color=color,
            line_width=2,
            annotation_text=annotation,
            annotation_position="right",
            annotation=dict(
                font=dict(size=11, color=color),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor=color,
                borderwidth=1
            ),
            row=row,
            col=1 if row else None
        )
    
    def create_signals_comparison(self, signals_with_data):
        """
        Create comparison chart of multiple signals
        
        Args:
            signals_with_data: List of (signal, df) tuples
            
        Returns:
            HTML with comparison table and mini charts
        """
        try:
            html_parts = []
            
            # Add comparison table
            html_parts.append("""
            <div class="signals-comparison">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Stock</th>
                            <th>Pattern</th>
                            <th>Recommendation</th>
                            <th>Confidence</th>
                            <th>Expected Return</th>
                            <th>Sentiment</th>
                        </tr>
                    </thead>
                    <tbody>
            """)
            
            for i, (signal, _) in enumerate(signals_with_data, 1):
                rec_badge = {
                    'STRONG_BUY': 'success',
                    'BUY': 'primary',
                    'WEAK_BUY': 'warning',
                    'HOLD': 'secondary'
                }.get(signal.recommendation, 'secondary')
                
                sent_badge = 'success' if signal.sentiment_raw > 0 else 'danger'
                
                html_parts.append(f"""
                    <tr>
                        <td><b>{i}</b></td>
                        <td><b>{signal.ticker}</b></td>
                        <td>{signal.pattern_type}</td>
                        <td><span class="badge bg-{rec_badge}">{signal.recommendation}</span></td>
                        <td>{signal.final_confidence:.1%}</td>
                        <td>{signal.predicted_return*100:+.1f}%</td>
                        <td><span class="badge bg-{sent_badge}">{signal.sentiment_label}</span></td>
                    </tr>
                """)
            
            html_parts.append("""
                    </tbody>
                </table>
            </div>
            """)
            
            # Add individual charts
            for signal, df in signals_with_data:
                chart_html = self.create_pattern_chart(df, signal)
                html_parts.append(f"""
                <div class="signal-chart mb-5">
                    <hr class="my-4">
                    {chart_html}
                </div>
                """)
            
            return '\n'.join(html_parts)
        
        except Exception as e:
            logger.error(f"Error creating comparison: {e}")
            return f"<div class='alert alert-danger'>Error: {e}</div>"


# Test code
if __name__ == '__main__':
    print("Testing PatternChartGenerator...")
    
    # This would normally be tested with real data
    print("[OK] PatternChartGenerator ready")
    print("Use in Flask app or workflow script")

