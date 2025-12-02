"""
Email Notification Service
Sends email notifications for trading events
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"✅ Loaded environment variables from {env_path}")
    else:
        logger.warning(f"⚠️  .env file not found at {env_path}")
except ImportError:
    logger.warning("⚠️  python-dotenv not installed. Using system environment variables.")

# Email configuration (from environment variables or config)
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')  # Your email
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')  # App password
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
FROM_NAME = os.getenv('FROM_NAME', 'SuperTrend Trading')


class EmailService:
    """Email notification service"""
    
    def __init__(self):
        self.enabled = bool(SMTP_USER and SMTP_PASSWORD)
        if not self.enabled:
            logger.warning("Email service not configured. Set SMTP_USER and SMTP_PASSWORD environment variables.")
    
    def send_email(self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None):
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text fallback (optional)
        """
        if not self.enabled:
            logger.warning(f"Email not sent (service disabled): {subject} to {to_email}")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_body:
                part1 = MIMEText(text_body, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(html_body, 'html')
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_trade_signals_email(self, to_email: str, signals: List[Dict], strategy: str):
        """Send email for new trade signals"""
        
        subject = f"🚀 {len(signals)} New Trade Signals Found - {strategy}"
        
        # Build signals table
        signals_html = ""
        for signal in signals[:10]:  # Limit to 10 signals in email
            signals_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">{signal.get('symbol', 'N/A')}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">₹{signal.get('entry_price', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">₹{signal.get('stop_loss', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">₹{signal.get('target', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">{signal.get('rr_ratio', 0):.1f}:1</td>
            </tr>
            """
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px;">📈 SuperTrend Trading</h1>
                    <p style="margin: 10px 0 0 0; font-size: 14px;">New Trade Opportunities Found!</p>
                </div>
                
                <div style="background: #f9fafb; padding: 20px; margin-top: 20px; border-radius: 10px;">
                    <h2 style="color: #667eea; margin-top: 0;">🚀 {len(signals)} New Signals</h2>
                    <p><strong>Strategy:</strong> {strategy}</p>
                    <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
                
                <div style="margin-top: 20px;">
                    <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden;">
                        <thead>
                            <tr style="background: #f3f4f6;">
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Symbol</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Entry</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">SL</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Target</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">R:R</th>
                            </tr>
                        </thead>
                        <tbody>
                            {signals_html}
                        </tbody>
                    </table>
                    {f'<p style="color: #666; font-size: 13px; margin-top: 10px;">Showing top 10 signals. Total: {len(signals)}</p>' if len(signals) > 10 else ''}
                </div>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="http://localhost:8000/scanner" style="display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        View All Signals
                    </a>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;">
                    <p style="margin: 0; font-size: 13px; color: #856404;">
                        <strong>⚠️ Disclaimer:</strong> This is an automated notification. Please review all signals carefully before trading. Past performance does not guarantee future results.
                    </p>
                </div>
                
                <div style="margin-top: 20px; text-align: center; color: #666; font-size: 12px;">
                    <p>You're receiving this because you enabled trade signal notifications.</p>
                    <p><a href="http://localhost:8000/profile#notifications" style="color: #667eea;">Manage notification preferences</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        SuperTrend Trading - New Trade Signals
        
        {len(signals)} new signals found for {strategy}
        Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
        
        View signals at: http://localhost:8000/scanner
        
        Manage notifications: http://localhost:8000/profile#notifications
        """
        
        return self.send_email(to_email, subject, html_body, text_body)
    
    def send_trade_exit_email(self, to_email: str, trade: Dict, exit_type: str):
        """
        Send email for trade exit (SL or Target hit)
        
        Args:
            to_email: Recipient email
            trade: Trade data
            exit_type: 'sl' or 'target'
        """
        
        is_profit = exit_type == 'target'
        symbol = trade.get('symbol', 'Unknown')
        entry_price = trade.get('entry_price', 0)
        exit_price = trade.get('exit_price', 0)
        pnl = trade.get('pnl', 0)
        pnl_pct = trade.get('pnl_pct', 0)
        
        emoji = "🎯" if is_profit else "🛑"
        color = "#10b981" if is_profit else "#ef4444"
        status = "Target Hit" if is_profit else "Stop Loss Hit"
        
        subject = f"{emoji} Trade Exit: {symbol} - {status}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: {color}; color: white; padding: 30px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0; font-size: 32px;">{emoji}</h1>
                    <h2 style="margin: 10px 0; font-size: 24px;">{status}</h2>
                    <p style="margin: 0; font-size: 18px; font-weight: bold;">{symbol}</p>
                </div>
                
                <div style="background: #f9fafb; padding: 20px; margin-top: 20px; border-radius: 10px;">
                    <h3 style="margin-top: 0; color: #333;">Trade Summary</h3>
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 8px 0;"><strong>Entry Price:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">₹{entry_price:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Exit Price:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">₹{exit_price:.2f}</td>
                        </tr>
                        <tr style="border-top: 2px solid #e5e7eb;">
                            <td style="padding: 8px 0; font-size: 18px;"><strong>P&L:</strong></td>
                            <td style="padding: 8px 0; text-align: right; font-size: 18px; font-weight: bold; color: {color};">
                                ₹{abs(pnl):.2f} ({'+' if pnl > 0 else ''}{pnl_pct:.2f}%)
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 20px; text-align: center;">
                    <a href="http://localhost:8000/trades" style="display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        View All Trades
                    </a>
                </div>
                
                <div style="margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                    <p>You're receiving this because you enabled trade exit notifications.</p>
                    <p><a href="http://localhost:8000/profile#notifications" style="color: #667eea;">Manage notification preferences</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        SuperTrend Trading - Trade Exit
        
        {status}: {symbol}
        
        Entry Price: ₹{entry_price:.2f}
        Exit Price: ₹{exit_price:.2f}
        P&L: ₹{abs(pnl):.2f} ({'+' if pnl > 0 else ''}{pnl_pct:.2f}%)
        
        View trades at: http://localhost:8000/trades
        """
        
        return self.send_email(to_email, subject, html_body, text_body)
    
    def send_daily_summary_email(self, to_email: str, summary: Dict):
        """Send daily portfolio summary email"""
        
        subject = f"📊 Daily Trading Summary - {datetime.now().strftime('%B %d, %Y')}"
        
        total_trades = summary.get('total_trades', 0)
        open_trades = summary.get('open_trades', 0)
        closed_today = summary.get('closed_today', 0)
        total_pnl = summary.get('total_pnl', 0)
        win_rate = summary.get('win_rate', 0)
        
        pnl_color = "#10b981" if total_pnl >= 0 else "#ef4444"
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px;">📊 Daily Trading Summary</h1>
                    <p style="margin: 10px 0 0 0;">{datetime.now().strftime('%B %d, %Y')}</p>
                </div>
                
                <div style="background: #f9fafb; padding: 20px; margin-top: 20px; border-radius: 10px;">
                    <h2 style="margin-top: 0; color: #333;">Portfolio Overview</h2>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px;">
                        <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb;">
                            <div style="color: #666; font-size: 12px;">Total Trades</div>
                            <div style="font-size: 24px; font-weight: bold; color: #667eea;">{total_trades}</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb;">
                            <div style="color: #666; font-size: 12px;">Open Positions</div>
                            <div style="font-size: 24px; font-weight: bold; color: #667eea;">{open_trades}</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb;">
                            <div style="color: #666; font-size: 12px;">Closed Today</div>
                            <div style="font-size: 24px; font-weight: bold; color: #667eea;">{closed_today}</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb;">
                            <div style="color: #666; font-size: 12px;">Win Rate</div>
                            <div style="font-size: 24px; font-weight: bold; color: #667eea;">{win_rate:.1f}%</div>
                        </div>
                    </div>
                    
                    <div style="background: {pnl_color}; color: white; padding: 20px; border-radius: 8px; margin-top: 20px; text-align: center;">
                        <div style="font-size: 14px; opacity: 0.9;">Today's P&L</div>
                        <div style="font-size: 32px; font-weight: bold;">{pnl_emoji} ₹{abs(total_pnl):.2f}</div>
                    </div>
                </div>
                
                <div style="margin-top: 20px; text-align: center;">
                    <a href="http://localhost:8000/dashboard" style="display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        View Dashboard
                    </a>
                </div>
                
                <div style="margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                    <p>You're receiving this daily summary email.</p>
                    <p><a href="http://localhost:8000/profile#notifications" style="color: #667eea;">Manage notification preferences</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        SuperTrend Trading - Daily Summary
        {datetime.now().strftime('%B %d, %Y')}
        
        Total Trades: {total_trades}
        Open Positions: {open_trades}
        Closed Today: {closed_today}
        Win Rate: {win_rate:.1f}%
        Today's P&L: ₹{abs(total_pnl):.2f}
        
        View dashboard: http://localhost:8000/dashboard
        """
        
        return self.send_email(to_email, subject, html_body, text_body)


# Global email service instance
email_service = EmailService()

