# Quick Start Guide - ML Pattern Trading System

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies (2 minutes)

```bash
cd ML
pip install -r requirements.txt
```

**Important**: TA-Lib needs manual installation:
- Windows: Download wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
- Linux: `sudo apt-get install ta-lib`
- Mac: `brew install ta-lib`

### Step 2: Setup System (30 seconds)

```bash
python run_complete_workflow.py setup
```

Creates database and directories.

### Step 3: Scan for Patterns (5-10 minutes)

```bash
python run_complete_workflow.py scan --universe FNO
```

Fetches data for F&O stocks and detects patterns.

### Step 4: Review Patterns (15-20 minutes for first batch)

```bash
python run_complete_workflow.py review
```

Open browser: **http://localhost:5000**

**Quick Review Guide**:
- Press `V` for valid pattern
- Press `X` for invalid pattern
- Press `1-5` for quality rating
- Press `Space` to skip

**Goal for first session**: Review 50-100 patterns

### Step 5: Continue Building Dataset

**Over next 2-3 weeks**:
- Review 50-100 patterns daily (15-20 minutes/day)
- Target: 500-1000 validated patterns
- Track progress in review interface

### Step 6: Train Models (when you have 500+ patterns)

```bash
python run_complete_workflow.py train
```

Trains all 3 ML models on your validated dataset.

**Time**: 5-10 minutes for 500 patterns

### Step 7: Generate Signals

```bash
python run_complete_workflow.py signals --universe FNO
```

Generates trading signals using trained models.

**Output**: `signals_YYYYMMDD.csv` with ranked opportunities

## 📊 Daily Workflow (After Initial Setup)

```bash
# Morning routine (2 minutes)
python signal_generator.py --universe FNO --load-models

# Weekly performance check (1 minute)
python performance/tracker.py
```

## 🎯 Success Checklist

### Week 1
- [ ] System setup complete
- [ ] First pattern scan done
- [ ] Reviewed 100+ patterns
- [ ] Comfortable with review interface

### Weeks 2-3
- [ ] Reviewed 500+ patterns
- [ ] Understood pattern quality criteria
- [ ] Dataset has diverse patterns

### Week 4
- [ ] Trained first ML models
- [ ] Generated first signals
- [ ] Started paper trading

### Months 2-3
- [ ] Continuous signal generation
- [ ] Performance tracking active
- [ ] Model accuracy monitored

## 💡 Pro Tips

1. **Review Quality > Speed**: Accurate labels are more important than quantity
2. **Consistency**: Review patterns daily for better learning
3. **Diversity**: Include various sectors and market conditions
4. **Paper Trade First**: Never go live without testing
5. **Track Everything**: Monitor actual vs predicted outcomes

## 🔧 Common Issues

**TA-Lib import error**:
```bash
# Install system package first, then pip install
pip install TA-Lib
```

**No patterns detected**:
- Check data fetching in logs
- Verify yfinance is working
- Try single stock: `python pattern_detection/scanner.py --ticker RELIANCE`

**Review interface not loading**:
```bash
# Check if port 5000 is free
# Try different port: edit review_interface/app.py, change port=5000
```

## 📚 Next Steps

After completing quickstart:
1. Read full [README.md](README.md)
2. Understand configuration options in `config.py`
3. Review pattern detection logic in `pattern_detection/`
4. Explore feature engineering in `feature_engineering/`

## 🎓 Learning Path

**Beginner**: 
- Focus on pattern review quality
- Understand basic patterns (hammer, engulfing, etc.)
- Build dataset to 500+ patterns

**Intermediate**:
- Customize feature engineering
- Tune model parameters
- Analyze pattern performance by sector

**Advanced**:
- Add custom chart patterns
- Implement ensemble models
- Optimize position sizing algorithms

---

**Time to First Signal**: 2-4 weeks (with daily review)  
**Time to Live Trading**: 2-3 months (recommended)  
**Expected Daily Effort**: 15-20 minutes pattern review + 2 minutes signal gen

**Remember**: Building a quality dataset takes time, but it's the foundation of the entire system!

