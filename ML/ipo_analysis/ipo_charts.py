"""
IPO Analysis Visualizations
Create interactive Plotly charts for IPO buy-and-hold analysis
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict


class IPOChartGenerator:
    """Generate interactive charts for IPO analysis"""
    
    def __init__(self, theme: str = 'plotly_white'):
        """
        Initialize chart generator
        
        Args:
            theme: Plotly theme (plotly, plotly_white, plotly_dark, etc.)
        """
        self.theme = theme
    
    def create_returns_bar_chart(self, df: pd.DataFrame, top_n: int = 20) -> str:
        """
        Create bar chart showing returns for top/bottom stocks
        
        Args:
            df: DataFrame with analysis results
            top_n: Number of top/bottom stocks to show
            
        Returns:
            HTML string with Plotly chart
        """
        # Get top and bottom performers
        df_sorted = df.sort_values('cagr', ascending=False)
        df_display = pd.concat([
            df_sorted.head(top_n // 2),
            df_sorted.tail(top_n // 2)
        ])
        
        # Color code by profit/loss
        colors = ['green' if x > 0 else 'red' for x in df_display['cagr']]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df_display['ticker'],
            y=df_display['cagr'],
            marker_color=colors,
            text=[f"{x:.1f}%" for x in df_display['cagr']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>CAGR: %{y:.2f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title=f'Top {top_n//2} & Bottom {top_n//2} Performers (CAGR %)',
            xaxis_title='Stock',
            yaxis_title='CAGR (%)',
            template=self.theme,
            height=500,
            showlegend=False,
            hovermode='x'
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id='returns_bar_chart')
    
    def create_portfolio_growth_chart(self, df: pd.DataFrame, summary: Dict) -> str:
        """
        Create line chart showing portfolio value growth over time
        
        Args:
            df: DataFrame with analysis results
            summary: Portfolio summary dict
            
        Returns:
            HTML string with Plotly chart
        """
        # Create timeline of investments and current values
        timeline_data = []
        
        for _, row in df.iterrows():
            # Add listing point
            timeline_data.append({
                'date': row['listing_date'],
                'invested': row['invested_amount'],
                'value': row['invested_amount']
            })
            
            # Add current value point
            timeline_data.append({
                'date': pd.Timestamp.now().date(),
                'invested': row['invested_amount'],
                'value': row['current_value']
            })
        
        # Group by date and calculate cumulative values
        df_timeline = pd.DataFrame(timeline_data)
        df_timeline = df_timeline.groupby('date').sum().reset_index()
        df_timeline = df_timeline.sort_values('date')
        df_timeline['cumulative_invested'] = df_timeline['invested'].cumsum()
        df_timeline['cumulative_value'] = df_timeline['value'].cumsum()
        
        fig = go.Figure()
        
        # Invested amount line
        fig.add_trace(go.Scatter(
            x=df_timeline['date'],
            y=df_timeline['cumulative_invested'],
            mode='lines+markers',
            name='Total Invested',
            line=dict(color='blue', width=2),
            hovertemplate='%{x}<br>Invested: Rs.%{y:,.0f}<extra></extra>'
        ))
        
        # Current value line
        fig.add_trace(go.Scatter(
            x=df_timeline['date'],
            y=df_timeline['cumulative_value'],
            mode='lines+markers',
            name='Current Value',
            line=dict(color='green', width=2),
            fill='tonexty',
            hovertemplate='%{x}<br>Value: Rs.%{y:,.0f}<extra></extra>'
        ))
        
        fig.update_layout(
            title='Portfolio Growth Over Time',
            xaxis_title='Date',
            yaxis_title='Amount (Rs.)',
            template=self.theme,
            height=500,
            hovermode='x unified',
            legend=dict(x=0.01, y=0.99)
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id='portfolio_growth_chart')
    
    def create_profit_loss_pie_chart(self, df: pd.DataFrame) -> str:
        """
        Create pie chart showing profit vs loss distribution
        
        Args:
            df: DataFrame with analysis results
            
        Returns:
            HTML string with Plotly chart
        """
        profit_count = len(df[df['absolute_return'] > 0])
        loss_count = len(df[df['absolute_return'] <= 0])
        
        fig = go.Figure(data=[go.Pie(
            labels=['Profitable', 'Loss Making'],
            values=[profit_count, loss_count],
            marker_colors=['green', 'red'],
            hole=0.4,
            textinfo='label+percent+value',
            hovertemplate='%{label}<br>Count: %{value}<br>Percent: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title='Win Rate: Profitable vs Loss Making Stocks',
            template=self.theme,
            height=400,
            annotations=[dict(text=f'{profit_count}/{len(df)}', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id='profit_loss_pie')
    
    def create_returns_distribution_histogram(self, df: pd.DataFrame) -> str:
        """
        Create histogram showing distribution of returns
        
        Args:
            df: DataFrame with analysis results
            
        Returns:
            HTML string with Plotly chart
        """
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=df['cagr'],
            nbinsx=20,
            marker_color='steelblue',
            hovertemplate='CAGR: %{x:.1f}%<br>Count: %{y}<extra></extra>'
        ))
        
        # Add vertical line for mean
        mean_cagr = df['cagr'].mean()
        fig.add_vline(
            x=mean_cagr,
            line_dash='dash',
            line_color='red',
            annotation_text=f'Mean: {mean_cagr:.1f}%',
            annotation_position='top'
        )
        
        fig.update_layout(
            title='Distribution of Returns (CAGR)',
            xaxis_title='CAGR (%)',
            yaxis_title='Number of Stocks',
            template=self.theme,
            height=400,
            showlegend=False
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id='returns_distribution')
    
    def create_investment_timeline_gantt(self, df: pd.DataFrame) -> str:
        """
        Create Gantt chart showing when each stock was bought
        
        Args:
            df: DataFrame with analysis results (sorted by CAGR)
            
        Returns:
            HTML string with Plotly chart
        """
        # Prepare data for Gantt chart
        df_sorted = df.sort_values('cagr', ascending=True).tail(20)  # Top 20
        
        gantt_data = []
        for _, row in df_sorted.iterrows():
            gantt_data.append(dict(
                Task=row['ticker'],
                Start=row['listing_date'],
                Finish=pd.Timestamp.now().date(),
                CAGR=row['cagr']
            ))
        
        df_gantt = pd.DataFrame(gantt_data)
        
        # Color by CAGR
        fig = px.timeline(
            df_gantt,
            x_start='Start',
            x_end='Finish',
            y='Task',
            color='CAGR',
            color_continuous_scale='RdYlGn',
            title='Investment Timeline (Top 20 by CAGR)'
        )
        
        fig.update_layout(
            template=self.theme,
            height=600,
            xaxis_title='Date',
            yaxis_title='Stock',
            coloraxis_colorbar=dict(title='CAGR %')
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id='investment_timeline')

