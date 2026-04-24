import pandas as pd
import numpy as np
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight

from shared.data import fetch_all
from orb.strategy import run_strategy
from orb.backtest import run_backtest, performance_report
from orb.features import build_feature_matrix
from orb.config import TIME_EXIT_CUTOFF

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

FEATURE_COLS = [
    "range_size_pct",
    "orb_body_ratio",
    "orb_upper_wick_ratio",
    "orb_lower_wick_ratio",
    "gap_pct",
    "orb_volume",
    "volume_ratio",
    "day_of_week",
    "signal_encoded",
    "ticker_encoded",
    "nifty_orb_return",
    "nifty_orb_range",
    "volatility_5d",

]


def time_split(feature_df: pd.DataFrame, train_ratio: float = 0.8):
    """
    Splits feature_df into train and test based on time, not randomly

    Returns (train, test)
    """

    all_dates = sorted(feature_df['date'].unique())
    cutoff_idx = int(len(all_dates) * train_ratio)
    cutoff_date = all_dates[cutoff_idx]
    
    train_df = feature_df[feature_df['date'] < cutoff_date]
    test_df = feature_df[feature_df['date'] >= cutoff_date]

    print(f'Train: {len(train_df)}: {all_dates[0]} -> {all_dates[cutoff_idx-1]}')
    print(f'Test: {len(test_df)}: {all_dates[cutoff_idx]} -> {all_dates[-1]}')

    return train_df, test_df

def train_model(train_df: pd.DataFrame, label_encoder: LabelEncoder) -> XGBClassifier:
    """
    n_estimators = 300, max_depth = 4, learning_rate = 0.05, subsample = 0.8 -> each tree trains random 80% of rows
    colsample_by_tree = 0.8 -> each tree trains uses random 80% of features
    use_label_encoder = False & eval_metric = "mlogloss" required for multi-class classification in modern XGBoost to avoid deprecation warnings.
    
    returns the fitted XGBClassifier
    """

    X_train = train_df[FEATURE_COLS]
    y_train = label_encoder.transform(train_df['label'])

    model = XGBClassifier(
        n_estimators = 300,
        max_depth = 4,
        learning_rate = 0.05,
        subsample = 0.8,
        colsample_bytree = 0.8,
        use_label_encoder = False,
        eval_metric = "mlogloss", 
        random_state = 42,
        verbosity = 0

    )
    classes = np.unique(y_train)
    weights = compute_class_weight(class_weight='balanced', classes=classes, y=y_train)
    sample_weights = [weights[i] for i in y_train]

    model.fit(X_train, y_train, sample_weight=sample_weights)
    return model

def evaluate_model(model: XGBClassifier, test_df: pd.DataFrame, label_encoder: LabelEncoder) -> pd.DataFrame:
    """
    prints classification report and confusion matrix
    also predicted labels and TARGET prob so we can use it for filtered_backtest
    """

    X_test = test_df[FEATURE_COLS]
    y_test = label_encoder.transform(test_df['label'])

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)

    target_class_idx = list(label_encoder.classes_).index("TARGET")

    print("\n=== Model Evaluation ===")
    print(classification_report(
        y_test, y_pred, 
        target_names = label_encoder.classes_
    ))

    print("Confusion Matrix (Rows -> Actual, Columns -> Predicted):")
    cm = confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(
        cm, 
        index = [f'actual_{c}' for c in label_encoder.classes_],
        columns = [f'prediction_{c}' for c in label_encoder.classes_]
    )
    print(cm_df.to_string())

    test_df = test_df.copy()
    test_df['predicted_label'] = label_encoder.inverse_transform(y_pred)
    test_df['target_prob'] = y_prob[:, target_class_idx]

    return test_df

def feature_importance(model: XGBClassifier) -> None:
    importance = pd.Series(
        model.feature_importances_,
        index = FEATURE_COLS,

    ).sort_values(ascending=False)
    print("\n=== Feature Importance ===")
    for feat, score in importance.items():
        bar = "█" * int(score * 100)
        print(f"  {feat:<25} {score:.4f}  {bar}")
 

def filtered_backtest(test_df : pd.DataFrame, trades: pd.DataFrame, signals: pd.DataFrame, data: dict, threshold: float = 0.5) -> None:
    approved = test_df[test_df["target_prob"] >= threshold][["date", "ticker"]]

    test_dates = test_df['date'].unique()
    test_trades = trades[trades['date'].isin(test_dates)].copy()
    test_signals = signals[signals['date'].isin(test_dates)].copy()

    approved["_keep"] = True
    filtered_signals = test_signals.merge(
        approved, on=['date', 'ticker'], how='left'
    )
    filtered_signals = filtered_signals[filtered_signals['_keep'] == True].drop(columns=['_keep'])
    print(f"\n=== Filtered Backtest (threshold={threshold}) ===")
    print(f"Test period signals total : {len(test_signals[test_signals['signal'] != 'NONE'])}")
    print(f"Model-approved signals    : {len(filtered_signals[filtered_signals['signal'] != 'NONE'])}")
 
    if filtered_signals.empty:
        print("No approved signals — try lowering the threshold.")
        return
 
    filtered_trades = run_backtest(filtered_signals, data, time_exit_hour=TIME_EXIT_CUTOFF)
 
    print("\n--- Unfiltered (test period, all signals) ---")
    performance_report(test_trades)
 
    print("--- Filtered (model-approved signals only) ---")
    performance_report(filtered_trades)
 
    # Lift summary
    unfiltered_net  = test_trades["net_pnl"].sum()
    filtered_net    = filtered_trades["net_pnl"].sum()
    unfiltered_exp  = test_trades["net_pnl"].mean()
    filtered_exp    = filtered_trades["net_pnl"].mean() if len(filtered_trades) else 0
 
    print("=== ML Filter Lift Summary ===")
    print(f"  Trades           : {len(test_trades)} → {len(filtered_trades)}")
    print(f"  Net P&L          : ₹{unfiltered_net:.2f} → ₹{filtered_net:.2f}")
    print(f"  Expectancy/trade : ₹{unfiltered_exp:.2f} → ₹{filtered_exp:.2f}")
    lift = filtered_exp - unfiltered_exp
    print(f"  Expectancy lift  : ₹{lift:+.2f} per trade")
    print("=" * 45)

    filtered_trades.to_csv(OUTPUT_DIR/"ml_filtered_trades.csv", index=False)
    print("Full trade log saved to ml_filtered_trades.csv")

 
if __name__ == "__main__":
    # ── Step 1: Load data and run base strategy + backtest ───────────────────
    print("Fetching data...")
    data = fetch_all(interval="1h")
 
    print("Running strategy...")
    signals = run_strategy(data)
 
    print("Running backtest...")
    trades = run_backtest(signals, data, time_exit_hour=TIME_EXIT_CUTOFF)
 
    # ── Step 2: Build feature matrix ─────────────────────────────────────────
    print("\nBuilding feature matrix...")
    feature_df = build_feature_matrix(signals, trades, data)
 
    # ── Step 3: Time-based train/test split ──────────────────────────────────
    print("\nSplitting by time...")
    train_df, test_df = time_split(feature_df, train_ratio=0.8)
 
    # ── Step 4: Encode labels ────────────────────────────────────────────────
    # XGBoost needs integer labels, not strings.
    # LabelEncoder maps TARGET→1, STOP→0, TIME→2 (alphabetical by default).
    # We fit on all possible labels (not just train) so encoding is consistent.
    label_encoder = LabelEncoder()
    label_encoder.fit(feature_df["label"])
    print(f"\nLabel classes: {list(label_encoder.classes_)}")
 
    # ── Step 5: Train model ──────────────────────────────────────────────────
    print("\nTraining XGBoost...")
    model = train_model(train_df, label_encoder)
    print("Training complete.")
 
    # ── Step 6: Evaluate on test set ─────────────────────────────────────────
    test_df = evaluate_model(model, test_df, label_encoder)
 
    # ── Step 7: Feature importance ───────────────────────────────────────────
    feature_importance(model)
 
    # ── Step 8: Filtered backtest ────────────────────────────────────────────
    filtered_backtest(test_df, trades, signals, data, threshold=0.5)
 


