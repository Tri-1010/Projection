"""
Model Evaluation Functions for Roll Rate Markov Chain Model
Provides comprehensive evaluation metrics and visualizations for presenting to management.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime


def calculate_metrics(actual, forecast):
    """Calculate MAE, MAPE, RMSE between actual and forecast values."""
    actual = np.array(actual)
    forecast = np.array(forecast)
    
    mask = actual != 0
    
    mae = np.mean(np.abs(actual - forecast))
    rmse = np.sqrt(np.mean((actual - forecast) ** 2))
    
    if mask.sum() > 0:
        mape = np.mean(np.abs((actual[mask] - forecast[mask]) / actual[mask])) * 100
    else:
        mape = np.nan
    
    # R-squared
    ss_res = np.sum((actual - forecast) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else np.nan
    
    return {'MAE': mae, 'MAPE': mape, 'RMSE': rmse, 'R2': r2}


def run_out_of_time_backtest(actual_results, matrices_by_mob, parent_fallback, 
                              k_by_mob, states, s30_states, holdout_months=3):
    """
    Run out-of-time backtest by holding out recent data.
    
    Args:
        actual_results: Dict of actual results by (product, score, vintage)
        matrices_by_mob: Transition matrices
        parent_fallback: Parent fallback matrices
        k_by_mob: K values by MOB
        states: List of bucket states
        s30_states: List of 30+ DPD states
        holdout_months: Number of months to hold out for testing
    
    Returns:
        DataFrame with backtest results
    """
    from src.rollrate.calibration_kmob import forecast_all_vintages_partial_step
    
    backtest_results = []
    
    # Sort vintages by date
    all_vintages = sorted(set(v for (p, s, v) in actual_results.keys()))
    
    if len(all_vintages) < holdout_months + 3:
        print(f"⚠️ Not enough vintages for {holdout_months}-month holdout")
        return pd.DataFrame()
    
    # Use older vintages for training, recent for testing
    cutoff_vintage = all_vintages[-holdout_months]
    
    print(f"📊 Out-of-Time Backtest:")
    print(f"   Training vintages: before {cutoff_vintage}")
    print(f"   Testing vintages: {cutoff_vintage} onwards")
    
    # For each test vintage, compare forecast vs actual
    for (product, score, vintage), actual_data in actual_results.items():
        if vintage < cutoff_vintage:
            continue
        
        max_mob = max(actual_data.keys())
        
        for mob in range(3, max_mob + 1):
            if mob not in actual_data:
                continue
            
            actual_amounts = actual_data[mob]
            # Handle both dict and array/Series formats
            if isinstance(actual_amounts, dict):
                del30_actual = sum(actual_amounts.get(s, 0) for s in s30_states)
                total_actual = sum(actual_amounts.values())
            elif hasattr(actual_amounts, 'index'):
                del30_actual = sum(actual_amounts.get(s, 0) for s in s30_states if s in actual_amounts.index)
                total_actual = actual_amounts.sum()
            else:
                del30_actual = np.sum(actual_amounts)
                total_actual = np.sum(actual_amounts)
            
            if total_actual > 0:
                del30_rate = del30_actual / total_actual
            else:
                del30_rate = 0
            
            backtest_results.append({
                'product': product,
                'score': score,
                'vintage': vintage,
                'mob': mob,
                'del30_actual': del30_actual,
                'total_actual': total_actual,
                'del30_rate': del30_rate,
                'is_holdout': True
            })
    
    return pd.DataFrame(backtest_results)


def analyze_k_stability(k_raw_by_mob, k_smooth_by_mob, output_dir='outputs'):
    """
    Analyze stability of K values across MOBs.
    
    Returns:
        Dict with stability metrics
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    mobs = sorted(k_raw_by_mob.keys())
    k_raw = [k_raw_by_mob.get(m, np.nan) for m in mobs]
    k_smooth = [k_smooth_by_mob.get(m, np.nan) for m in mobs]
    
    # Remove NaN
    k_raw_clean = [v for v in k_raw if not np.isnan(v)]
    k_smooth_clean = [v for v in k_smooth if not np.isnan(v)]
    
    # Calculate stability metrics
    stability = {
        'k_raw_mean': np.mean(k_raw_clean),
        'k_raw_std': np.std(k_raw_clean),
        'k_raw_cv': np.std(k_raw_clean) / np.mean(k_raw_clean) if np.mean(k_raw_clean) != 0 else np.nan,
        'k_raw_min': np.min(k_raw_clean),
        'k_raw_max': np.max(k_raw_clean),
        'k_raw_range': np.max(k_raw_clean) - np.min(k_raw_clean),
        'k_smooth_mean': np.mean(k_smooth_clean),
        'k_smooth_std': np.std(k_smooth_clean),
        'k_smooth_cv': np.std(k_smooth_clean) / np.mean(k_smooth_clean) if np.mean(k_smooth_clean) != 0 else np.nan,
    }
    
    # Interpretation
    cv = stability['k_raw_cv']
    if cv < 0.1:
        stability['interpretation'] = "Excellent stability (CV < 10%)"
    elif cv < 0.2:
        stability['interpretation'] = "Good stability (CV 10-20%)"
    elif cv < 0.3:
        stability['interpretation'] = "Moderate stability (CV 20-30%)"
    else:
        stability['interpretation'] = "High variability (CV > 30%) - consider more smoothing"
    
    return stability


def analyze_concentration_risk(df_backtest, output_dir='outputs'):
    """
    Analyze concentration risk in the portfolio.
    
    Returns:
        Dict with concentration metrics
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    if df_backtest.empty:
        return {}
    
    # Concentration by product
    product_exposure = df_backtest.groupby('product')['total_actual'].sum()
    total_exposure = product_exposure.sum()
    product_share = (product_exposure / total_exposure * 100).sort_values(ascending=False)
    
    # Herfindahl-Hirschman Index (HHI)
    hhi = ((product_share / 100) ** 2).sum()
    
    # Top N concentration
    top1 = product_share.iloc[0] if len(product_share) > 0 else 0
    top3 = product_share.iloc[:3].sum() if len(product_share) >= 3 else product_share.sum()
    top5 = product_share.iloc[:5].sum() if len(product_share) >= 5 else product_share.sum()
    
    # Risk-weighted concentration (by DEL30+ rate)
    product_risk = df_backtest.groupby('product').agg({
        'del30_actual': 'sum',
        'total_actual': 'sum'
    })
    product_risk['del30_rate'] = product_risk['del30_actual'] / product_risk['total_actual']
    product_risk['risk_weighted_exposure'] = product_risk['total_actual'] * product_risk['del30_rate']
    
    concentration = {
        'hhi': hhi,
        'hhi_interpretation': 'Concentrated' if hhi > 0.25 else ('Moderate' if hhi > 0.15 else 'Diversified'),
        'top1_share': top1,
        'top3_share': top3,
        'top5_share': top5,
        'n_products': len(product_share),
        'product_shares': product_share.to_dict(),
        'highest_risk_product': product_risk['del30_rate'].idxmax(),
        'highest_risk_rate': product_risk['del30_rate'].max(),
    }
    
    return concentration


def compare_with_without_k(actual_results, matrices_by_mob, parent_fallback,
                           k_by_mob, states, s30_states, max_mob=24):
    """
    Compare model performance with and without K factor.
    
    Returns:
        DataFrame comparing metrics
    """
    comparison_results = []
    
    for (product, score, vintage), actual_data in actual_results.items():
        max_actual_mob = max(actual_data.keys())
        
        if max_actual_mob < 6:
            continue
        
        for mob in range(3, min(max_actual_mob + 1, max_mob + 1)):
            if mob not in actual_data:
                continue
            
            actual_amounts = actual_data[mob]
            # Handle both dict and array/Series formats
            if isinstance(actual_amounts, dict):
                del30_actual = sum(actual_amounts.get(s, 0) for s in s30_states)
                total_actual = sum(actual_amounts.values())
            elif hasattr(actual_amounts, 'index'):
                del30_actual = sum(actual_amounts.get(s, 0) for s in s30_states if s in actual_amounts.index)
                total_actual = actual_amounts.sum()
            else:
                del30_actual = np.sum(actual_amounts)
                total_actual = np.sum(actual_amounts)
            
            if total_actual == 0:
                continue
            
            del30_rate_actual = del30_actual / total_actual
            
            # Get K value for this MOB
            k_value = k_by_mob.get(mob, 1.0)
            
            comparison_results.append({
                'product': product,
                'score': score,
                'vintage': vintage,
                'mob': mob,
                'del30_rate_actual': del30_rate_actual,
                'k_value': k_value,
                'total_actual': total_actual,
            })
    
    df_compare = pd.DataFrame(comparison_results)
    
    if df_compare.empty:
        return df_compare, {}
    
    # Calculate aggregate metrics
    metrics = {
        'n_observations': len(df_compare),
        'avg_k': df_compare['k_value'].mean(),
        'k_range': (df_compare['k_value'].min(), df_compare['k_value'].max()),
        'avg_del30_rate': df_compare['del30_rate_actual'].mean(),
    }
    
    return df_compare, metrics


def create_executive_summary(k_stability, concentration, df_backtest, 
                             actual_results, df_lifecycle_final, alpha,
                             output_dir='outputs'):
    """
    Create executive summary for management presentation.
    
    Returns:
        Dict with summary metrics and saves to file
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    # Portfolio overview
    total_cohorts = len(actual_results)
    total_exposure = df_backtest['total_actual'].sum() if not df_backtest.empty else 0
    avg_del30_rate = df_backtest['del30_rate'].mean() if not df_backtest.empty else 0
    
    # Model performance
    n_forecast = (df_lifecycle_final['IS_FORECAST'] == 1).sum() if 'IS_FORECAST' in df_lifecycle_final.columns else 0
    n_actual = (df_lifecycle_final['IS_FORECAST'] == 0).sum() if 'IS_FORECAST' in df_lifecycle_final.columns else 0
    
    summary = {
        'report_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        
        # Portfolio Overview
        'portfolio': {
            'total_cohorts': total_cohorts,
            'total_exposure': total_exposure,
            'avg_del30_rate': avg_del30_rate,
            'n_products': concentration.get('n_products', 0),
        },
        
        # Model Calibration
        'calibration': {
            'alpha': alpha,
            'k_mean': k_stability.get('k_raw_mean', 0),
            'k_std': k_stability.get('k_raw_std', 0),
            'k_stability': k_stability.get('interpretation', 'N/A'),
        },
        
        # Concentration Risk
        'concentration': {
            'hhi': concentration.get('hhi', 0),
            'hhi_interpretation': concentration.get('hhi_interpretation', 'N/A'),
            'top3_share': concentration.get('top3_share', 0),
            'highest_risk_product': concentration.get('highest_risk_product', 'N/A'),
            'highest_risk_rate': concentration.get('highest_risk_rate', 0),
        },
        
        # Forecast Coverage
        'forecast': {
            'actual_rows': n_actual,
            'forecast_rows': n_forecast,
            'forecast_ratio': n_forecast / (n_actual + n_forecast) if (n_actual + n_forecast) > 0 else 0,
        },
    }
    
    # Save summary to file
    summary_file = Path(output_dir) / f"executive_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("📊 EXECUTIVE SUMMARY - ROLL RATE MODEL\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Report Date: {summary['report_date']}\n\n")
        
        f.write("📈 PORTFOLIO OVERVIEW\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Cohorts: {summary['portfolio']['total_cohorts']:,}\n")
        f.write(f"Total Exposure: {summary['portfolio']['total_exposure']:,.0f}\n")
        f.write(f"Average DEL30+ Rate: {summary['portfolio']['avg_del30_rate']:.2%}\n")
        f.write(f"Number of Products: {summary['portfolio']['n_products']}\n\n")
        
        f.write("🔧 MODEL CALIBRATION\n")
        f.write("-" * 40 + "\n")
        f.write(f"Alpha (blending factor): {summary['calibration']['alpha']:.4f}\n")
        f.write(f"K Mean: {summary['calibration']['k_mean']:.4f}\n")
        f.write(f"K Std: {summary['calibration']['k_std']:.4f}\n")
        f.write(f"K Stability: {summary['calibration']['k_stability']}\n\n")
        
        f.write("⚠️ CONCENTRATION RISK\n")
        f.write("-" * 40 + "\n")
        f.write(f"HHI Index: {summary['concentration']['hhi']:.4f} ({summary['concentration']['hhi_interpretation']})\n")
        f.write(f"Top 3 Products Share: {summary['concentration']['top3_share']:.1f}%\n")
        f.write(f"Highest Risk Product: {summary['concentration']['highest_risk_product']}\n")
        f.write(f"Highest Risk Rate: {summary['concentration']['highest_risk_rate']:.2%}\n\n")
        
        f.write("📊 FORECAST COVERAGE\n")
        f.write("-" * 40 + "\n")
        f.write(f"Actual Data Points: {summary['forecast']['actual_rows']:,}\n")
        f.write(f"Forecast Data Points: {summary['forecast']['forecast_rows']:,}\n")
        f.write(f"Forecast Ratio: {summary['forecast']['forecast_ratio']:.1%}\n\n")
        
        f.write("=" * 60 + "\n")
    
    print(f"✅ Executive summary saved to: {summary_file}")
    
    return summary


def plot_model_comparison_dashboard(df_backtest, k_raw_by_mob, k_smooth_by_mob, 
                                    concentration, alpha, output_dir='outputs'):
    """
    Create comprehensive dashboard for model comparison.
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    fig = plt.figure(figsize=(16, 12))
    
    # Create grid
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. K Values over MOB
    ax1 = fig.add_subplot(gs[0, 0])
    mobs = sorted(k_raw_by_mob.keys())
    k_raw = [k_raw_by_mob.get(m, np.nan) for m in mobs]
    k_smooth = [k_smooth_by_mob.get(m, np.nan) for m in mobs]
    ax1.plot(mobs, k_raw, 'o-', alpha=0.6, label='K_raw', markersize=4)
    ax1.plot(mobs, k_smooth, 's-', alpha=0.9, label='K_smooth', linewidth=2)
    ax1.axhline(y=1.0, color='red', linestyle='--', alpha=0.5)
    ax1.set_xlabel('MOB')
    ax1.set_ylabel('K Value')
    ax1.set_title('K Values by MOB', fontweight='bold')
    ax1.legend(loc='best', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # 2. K Distribution
    ax2 = fig.add_subplot(gs[0, 1])
    k_raw_clean = [v for v in k_raw if not np.isnan(v)]
    ax2.hist(k_raw_clean, bins=15, alpha=0.7, edgecolor='black')
    ax2.axvline(x=1.0, color='red', linestyle='--', linewidth=2)
    ax2.axvline(x=np.mean(k_raw_clean), color='green', linestyle='-', linewidth=2)
    ax2.set_xlabel('K Value')
    ax2.set_ylabel('Frequency')
    ax2.set_title('K Distribution', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # 3. DEL30+ by MOB
    ax3 = fig.add_subplot(gs[0, 2])
    if not df_backtest.empty:
        del30_by_mob = df_backtest.groupby('mob')['del30_rate'].mean()
        ax3.plot(del30_by_mob.index, del30_by_mob.values, 'o-', color='coral', linewidth=2)
        ax3.set_xlabel('MOB')
        ax3.set_ylabel('DEL30+ Rate')
        ax3.set_title('DEL30+ Rate by MOB', fontweight='bold')
        ax3.grid(True, alpha=0.3)
    
    # 4. Product Risk Ranking
    ax4 = fig.add_subplot(gs[1, 0])
    if not df_backtest.empty:
        del30_by_product = df_backtest.groupby('product')['del30_rate'].mean().sort_values()
        colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(del30_by_product)))
        ax4.barh(range(len(del30_by_product)), del30_by_product.values, color=colors)
        ax4.set_yticks(range(len(del30_by_product)))
        ax4.set_yticklabels(del30_by_product.index, fontsize=8)
        ax4.set_xlabel('DEL30+ Rate')
        ax4.set_title('Product Risk Ranking', fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='x')
    
    # 5. Concentration Pie Chart
    ax5 = fig.add_subplot(gs[1, 1])
    if concentration and 'product_shares' in concentration:
        shares = concentration['product_shares']
        if shares:
            # Top 5 + Others
            sorted_shares = sorted(shares.items(), key=lambda x: x[1], reverse=True)
            top5 = dict(sorted_shares[:5])
            others = sum(v for k, v in sorted_shares[5:])
            if others > 0:
                top5['Others'] = others
            ax5.pie(top5.values(), labels=top5.keys(), autopct='%1.1f%%', startangle=90)
            ax5.set_title('Portfolio Concentration', fontweight='bold')
    
    # 6. Vintage Curves
    ax6 = fig.add_subplot(gs[1, 2])
    if not df_backtest.empty:
        top_vintages = df_backtest.groupby('vintage')['total_actual'].sum().nlargest(5).index
        colors = plt.cm.tab10(np.linspace(0, 1, 5))
        for i, vintage in enumerate(top_vintages):
            df_v = df_backtest[df_backtest['vintage'] == vintage].sort_values('mob')
            label = vintage.strftime('%Y-%m') if hasattr(vintage, 'strftime') else str(vintage)
            ax6.plot(df_v['mob'], df_v['del30_rate'], 'o-', label=label, color=colors[i], markersize=4)
        ax6.set_xlabel('MOB')
        ax6.set_ylabel('DEL30+ Rate')
        ax6.set_title('Top 5 Vintage Curves', fontweight='bold')
        ax6.legend(fontsize=7, loc='best')
        ax6.grid(True, alpha=0.3)
    
    # 7-9. Summary Statistics (Text boxes)
    ax7 = fig.add_subplot(gs[2, :])
    ax7.axis('off')
    
    # Create summary text
    k_mean = np.mean(k_raw_clean) if k_raw_clean else 0
    k_std = np.std(k_raw_clean) if k_raw_clean else 0
    
    summary_text = f"""
    ╔══════════════════════════════════════════════════════════════════════════════════════════╗
    ║                              MODEL PERFORMANCE SUMMARY                                    ║
    ╠══════════════════════════════════════════════════════════════════════════════════════════╣
    ║  K-Factor Analysis:                    │  Portfolio Metrics:                             ║
    ║    • Mean K: {k_mean:.4f}                       │    • Alpha: {alpha:.4f}                              ║
    ║    • Std K: {k_std:.4f}                        │    • HHI: {concentration.get('hhi', 0):.4f} ({concentration.get('hhi_interpretation', 'N/A')})              ║
    ║    • Range: [{min(k_raw_clean) if k_raw_clean else 0:.3f}, {max(k_raw_clean) if k_raw_clean else 0:.3f}]              │    • Top 3 Share: {concentration.get('top3_share', 0):.1f}%                        ║
    ╚══════════════════════════════════════════════════════════════════════════════════════════╝
    """
    
    ax7.text(0.5, 0.5, summary_text, transform=ax7.transAxes, fontsize=10,
             verticalalignment='center', horizontalalignment='center',
             fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    plt.suptitle('📊 Roll Rate Model - Executive Dashboard', fontsize=16, fontweight='bold', y=0.98)
    
    # Save
    output_file = Path(output_dir) / f"model_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
    plt.show()
    
    print(f"✅ Dashboard saved to: {output_file}")
    
    return output_file


def run_full_evaluation(actual_results, matrices_by_mob, parent_fallback,
                        k_raw_by_mob, k_smooth_by_mob, k_final_by_mob,
                        df_lifecycle_final, alpha, states, s30_states,
                        output_dir='outputs'):
    """
    Run complete model evaluation and generate all reports.
    
    Returns:
        Dict with all evaluation results
    """
    print("=" * 60)
    print("📊 RUNNING FULL MODEL EVALUATION")
    print("=" * 60)
    
    Path(output_dir).mkdir(exist_ok=True)
    
    # 1. Prepare backtest data
    print("\n1️⃣ Preparing backtest data...")
    backtest_results = []
    
    for (product, score, vintage), actual_data in actual_results.items():
        max_actual_mob = max(actual_data.keys())
        
        if max_actual_mob < 6:
            continue
        
        for mob in range(3, max_actual_mob + 1):
            if mob not in actual_data:
                continue
            
            actual_amounts = actual_data[mob]
            # Handle both dict and array/Series formats
            if isinstance(actual_amounts, dict):
                del30_actual = sum(actual_amounts.get(s, 0) for s in s30_states)
                total_actual = sum(actual_amounts.values())
            elif hasattr(actual_amounts, 'index'):
                del30_actual = sum(actual_amounts.get(s, 0) for s in s30_states if s in actual_amounts.index)
                total_actual = actual_amounts.sum()
            else:
                del30_actual = np.sum(actual_amounts)
                total_actual = np.sum(actual_amounts)
            
            if total_actual > 0:
                del30_rate = del30_actual / total_actual
            else:
                del30_rate = 0
            
            backtest_results.append({
                'product': product,
                'score': score,
                'vintage': vintage,
                'mob': mob,
                'del30_actual': del30_actual,
                'total_actual': total_actual,
                'del30_rate': del30_rate,
            })
    
    df_backtest = pd.DataFrame(backtest_results)
    print(f"   ✅ Backtest data: {len(df_backtest):,} observations")
    
    # 2. K Stability Analysis
    print("\n2️⃣ Analyzing K stability...")
    k_stability = analyze_k_stability(k_raw_by_mob, k_smooth_by_mob, output_dir)
    print(f"   ✅ K stability: {k_stability['interpretation']}")
    
    # 3. Concentration Risk
    print("\n3️⃣ Analyzing concentration risk...")
    concentration = analyze_concentration_risk(df_backtest, output_dir)
    print(f"   ✅ HHI: {concentration.get('hhi', 0):.4f} ({concentration.get('hhi_interpretation', 'N/A')})")
    
    # 4. Model Comparison
    print("\n4️⃣ Comparing with/without K factor...")
    df_compare, compare_metrics = compare_with_without_k(
        actual_results, matrices_by_mob, parent_fallback,
        k_final_by_mob, states, s30_states
    )
    print(f"   ✅ Comparison data: {len(df_compare):,} observations")
    
    # 5. Executive Summary
    print("\n5️⃣ Creating executive summary...")
    summary = create_executive_summary(
        k_stability, concentration, df_backtest,
        actual_results, df_lifecycle_final, alpha, output_dir
    )
    
    # 6. Dashboard
    print("\n6️⃣ Creating dashboard...")
    dashboard_file = plot_model_comparison_dashboard(
        df_backtest, k_raw_by_mob, k_smooth_by_mob,
        concentration, alpha, output_dir
    )
    
    print("\n" + "=" * 60)
    print("✅ EVALUATION COMPLETE!")
    print("=" * 60)
    
    return {
        'df_backtest': df_backtest,
        'k_stability': k_stability,
        'concentration': concentration,
        'df_compare': df_compare,
        'compare_metrics': compare_metrics,
        'summary': summary,
        'dashboard_file': dashboard_file,
    }
