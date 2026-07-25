# Defines source model workflow for train models.
"""
Train and evaluate multiple models for encrypted malware detection.
"""

import argparse
from pathlib import Path
import numpy as np, pandas as pd, yaml, json
from typing import Dict, List, Tuple, Any
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score, 
    f1_score,
    confusion_matrix,
    roc_curve,
    auc)
import xgboost as xgb, lightgbm as lgb
from sklearn.ensemble import VotingClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.feature_selection import RFECV
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import RandomizedSearchCV
from scipy.stats import randint, uniform
import joblib, os

import matplotlib.pyplot as plt, seaborn as sns

# Add imbalanced-learn support
from imblearn.over_sampling import SMOTE
from imblearn.combine import SMOTETomek
from sklearn.utils.class_weight import compute_class_weight


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load model configuration."""
    with open(config_path) as f:
        return yaml.safe_load(f)

def remove_correlated_features(features: pd.DataFrame, threshold: float = 0.95) -> pd.DataFrame:
    """Remove highly correlated features."""
    corr_matrix = features.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
    print(f"Removing {len(to_drop)} highly correlated features")
    return features.drop(to_drop, axis=1)

def load_data(features_path: Path, labels_path: Path) -> Tuple[pd.DataFrame, pd.Series]:
    """Load and preprocess features and labels."""
    features = pd.read_csv(features_path)
    labels = pd.read_csv(labels_path)
    
    # If 'file' column is missing in features, create synthetic IDs
    if 'file' not in features.columns:
        print("Warning: 'file' column not found in features. Generating synthetic file IDs.")
        features = features.reset_index().rename(columns={'index': 'file'})
        features['file'] = features['file'].apply(lambda x: f'large_sample_{int(x):05d}')

    # If 'file' missing in labels, try to infer
    if 'file' not in labels.columns and 'Id' in labels.columns:
        labels = labels.rename(columns={'Id': 'file'})

    if 'file' not in labels.columns:
        # If labels don't include file names, assume labels are aligned row-wise
        print("Warning: 'file' column not found in labels. Assuming row-wise alignment.")
        # create synthetic file ids for labels
        labels = labels.reset_index().rename(columns={'index': 'file'})
        labels['file'] = labels['file'].apply(lambda x: f'large_sample_{int(x):05d}')

    # Extract base_file
    features['base_file'] = features['file'].astype(str).apply(lambda x: x.split('.')[0])
    labels['base_file'] = labels['file'].astype(str).apply(lambda x: x.split('.')[0])
    
    # Merge features with labels
    merged = pd.merge(features, labels[['base_file', 'family']] if 'family' in labels.columns else labels[['base_file', labels.columns[-1]]], on='base_file', how='inner')
    print(f"Number of samples after matching: {len(merged)}")
    
    # Determine label column
    if 'family' in merged.columns:
        label_col = 'family'
    else:
        # use last column as label
        label_col = merged.columns[-1]
    
    # If family is multi-class or numeric classes, preserve; if strings 'Malware'/'Benign', convert to binary
    if merged[label_col].dtype == object:
        if set(merged[label_col].unique()) <= {'Malware', 'Benign'}:
            labels_series = (merged[label_col] == 'Malware').astype(int)
        else:
            labels_series = merged[label_col].astype(str)
    else:
        labels_series = merged[label_col]

    # Remove file-related columns
    drop_cols = [c for c in ['file', 'base_file', 'family'] if c in merged.columns]
    features_df = merged.drop(drop_cols + [label_col] if label_col in merged.columns else drop_cols, axis=1)

    # Remove constant columns
    nunique = features_df.nunique()
    constant_cols = nunique[nunique == 1].index
    print(f"Removing {len(constant_cols)} constant columns")
    features_df = features_df.drop(constant_cols, axis=1)

    # Remove zero columns 
    zero_cols = features_df.columns[(features_df == 0).all()]
    print(f"Removing {len(zero_cols)} zero-valued columns")
    features_df = features_df.drop(zero_cols, axis=1)

    # Handle NaN values
    nan_cols = features_df.isna().any()
    print(f"Found {nan_cols.sum()} columns with NaN values")
    features_df = features_df.fillna(0)  # Replace NaNs with 0s

    # Remove highly correlated features
    features_df = remove_correlated_features(features_df)

    return features_df, labels_series

def preprocess_data(features: pd.DataFrame, labels: pd.Series, test_size: float = 0.2,
                   sampling_strategy: str = 'none') -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    """Preprocess data and split into train/test sets.

    sampling_strategy: 'none' | 'smote' | 'smotetomek'
    Returns X_train, X_test, y_train, y_test, scaler
    """
    # Scale features
    scaler = StandardScaler()
    X = scaler.fit_transform(features)
    
    # If sampling is requested, apply it to the *unscaled* data (better practice: scale then sample or sample then scale depending on sampler; for SMOTE we scale first to keep numeric ranges stable)
    if sampling_strategy not in ('none', None):
        if sampling_strategy == 'smote':
            sampler = SMOTE(random_state=42)
        elif sampling_strategy == 'smotetomek':
            sampler = SMOTETomek(random_state=42)
        else:
            raise ValueError(f"Unknown sampling_strategy: {sampling_strategy}")
        
        # SMOTE expects 2D array X and 1D y
        X, labels = sampler.fit_resample(X, labels)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, labels, test_size=test_size, random_state=42, stratify=labels
    )
    
    return X_train, X_test, y_train, y_test, scaler

def train_random_forest(X_train: np.ndarray, y_train: pd.Series, 
                       config: Dict[str, Any]) -> RandomForestClassifier:
    """Train Random Forest model."""
    rf_params = config.get('random_forest', {})
    rf = RandomForestClassifier(
        n_estimators=rf_params.get('n_estimators', 100),
        max_depth=rf_params.get('max_depth', None),
        min_samples_split=rf_params.get('min_samples_split', 2),
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    return rf

def train_xgboost(X_train: np.ndarray, y_train: pd.Series,
                  config: Dict[str, Any]) -> xgb.XGBClassifier:
    """Train XGBoost model."""
    xgb_params = config.get('xgboost', {})
    xgb_model = xgb.XGBClassifier(
        n_estimators=xgb_params.get('n_estimators', 100),
        max_depth=xgb_params.get('max_depth', 6),
        learning_rate=xgb_params.get('learning_rate', 0.3),
        random_state=42,
        n_jobs=-1
    )
    xgb_model.fit(X_train, y_train)
    return xgb_model

def train_lightgbm(X_train: np.ndarray, y_train: pd.Series,
                   config: Dict[str, Any]) -> lgb.LGBMClassifier:
    """Train LightGBM model."""
    lgb_params = config.get('lightgbm', {})
    lgb_model = lgb.LGBMClassifier(
        n_estimators=lgb_params.get('n_estimators', 100),
        max_depth=lgb_params.get('max_depth', -1),
        learning_rate=lgb_params.get('learning_rate', 0.3),
        random_state=42,
        n_jobs=-1
    )
    lgb_model.fit(X_train, y_train)
    return lgb_model

def train_ensemble(models: List[Tuple[str, Any]], X_train: np.ndarray,
                  y_train: pd.Series) -> VotingClassifier:
    """Train ensemble model."""
    ensemble = VotingClassifier(
        estimators=models,
        voting='soft'
    )
    ensemble.fit(X_train, y_train)
    return ensemble

def evaluate_model(model: Any, X_test: np.ndarray, y_test: pd.Series,
                  model_name: str) -> Dict[str, float]:
    """Evaluate model and return metrics."""
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        'model': model_name,
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, average='weighted'),
        'recall': recall_score(y_test, y_pred, average='weighted'),
        'f1': f1_score(y_test, y_pred, average='weighted')
    }
    
    # Calculate ROC curve
    fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
    metrics['auc'] = auc(fpr, tpr)
    metrics['roc'] = {'fpr': fpr.tolist(), 'tpr': tpr.tolist()}
    
    # Get confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    metrics['confusion_matrix'] = cm.tolist()
    
    return metrics

def plot_confusion_matrix(cm: np.ndarray, model_name: str,
                         save_path: Path):
    """Plot and save confusion matrix."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.title(f'Confusion Matrix - {model_name}')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.savefig(save_path / f'{model_name.lower()}_confusion_matrix.png')
    plt.close()

def plot_roc_curves(metrics: List[Dict[str, Any]], save_path: Path):
    """Plot ROC curves for all models."""
    plt.figure(figsize=(10, 8))
    
    for metric in metrics:
        model_name = metric['model']
        fpr = metric['roc']['fpr']
        tpr = metric['roc']['tpr']
        auc_score = metric['auc']
        
        plt.plot(fpr, tpr, label=f'{model_name} (AUC = {auc_score:.2f})')
    
    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curves')
    plt.legend()
    plt.savefig(save_path / 'roc_curves.png')
    plt.close()

def save_results(metrics: List[Dict[str, Any]], save_path: Path):
    """Save evaluation results."""
    results = {
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics
    }
    
    with open(save_path / 'evaluation_results.json', 'w') as f:
        json.dump(results, f, indent=2)

def plot_feature_importance(model, feature_names: List[str], 
                          model_name: str, save_path: Path):
    """Plot feature importance."""
    if hasattr(model, 'feature_importances_'):
        importance = model.feature_importances_
        indices = np.argsort(importance)[::-1]
        
        plt.figure(figsize=(12, 6))
        plt.title(f'Feature Importance - {model_name}')
        plt.bar(range(len(indices)), importance[indices])
        plt.xticks(range(len(indices)), 
                  [feature_names[i] for i in indices], 
                  rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(save_path / f'{model_name.lower()}_feature_importance.png')
        plt.close()

def feature_selection_pipeline(features: pd.DataFrame, labels: pd.Series,
                               method: str = 'selectkbest', k: int = 200,
                               estimator=None, cv_folds: int = 5) -> pd.DataFrame:
    """Apply feature selection and return the reduced features DataFrame.

    method: 'selectkbest' or 'rfecv'
    - SelectKBest is fast and works well for high-dimensional data as an initial step.
    - RFECV is more thorough (recursive elimination with CV) but computationally expensive.

    We'll default to SelectKBest for speed; use RFECV when you need the most robust subset.
    """
    X = features.copy()
    y = labels.values

    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    X_num = X[numeric_cols]

    if method == 'selectkbest':
        k = min(k, X_num.shape[1])
        selector = SelectKBest(score_func=f_classif, k=k)
        X_selected = selector.fit_transform(X_num, y)
        selected_mask = selector.get_support()
        selected_cols = [c for c, keep in zip(numeric_cols, selected_mask) if keep]
        print(f"SelectKBest selected {len(selected_cols)} features (k={k})")
        return X[selected_cols]

    elif method == 'rfecv':
        if estimator is None:
            estimator = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42)
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
        rfecv = RFECV(estimator=estimator, step=0.1, cv=cv, scoring='f1_weighted', n_jobs=-1)
        rfecv.fit(X_num, y)
        selected_mask = rfecv.support_
        selected_cols = [c for c, keep in zip(numeric_cols, selected_mask) if keep]
        print(f"RFECV selected {len(selected_cols)} features (cv_folds={cv_folds})")
        return X[selected_cols]

    else:
        raise ValueError(f"Unknown method: {method}")

def hyperparameter_optimization(features: pd.DataFrame, labels: pd.Series,
                                sampling_strategy: str = 'smote',
                                feature_selection_method: str | None = None,
                                feature_selection_k: int = 200,
                                n_iter: int = 30,
                                cv_folds: int = 5,
                                random_state: int = 42) -> Dict[str, Any]:
    """Run RandomizedSearchCV for RF, XGB and LGBM and return best models and summary.

    This function supports optional feature selection (selectkbest or rfecv) and sampling.
    It performs stratified CV and uses `f1_weighted` as the optimization objective.
    """
    results = {}

    # 1) Optional feature selection
    X_df = features.copy()
    if feature_selection_method is not None:
        print(f"Running feature selection: {feature_selection_method} (k={feature_selection_k})")
        X_df = feature_selection_pipeline(X_df, labels, method=feature_selection_method, k=feature_selection_k)
        print(f"Feature selection reduced to {X_df.shape[1]} features")

    # 2) Preprocess & optionally sample (preprocess_data returns scaled arrays)
    X_train, X_test, y_train, y_test, scaler = preprocess_data(X_df, labels, sampling_strategy=sampling_strategy)

    # Note: RandomizedSearchCV expects unfitted estimators
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)

    # Define parameter distributions
    rf_param_dist = {
        'n_estimators': randint(100, 500),
        'max_depth': [None] + list(range(6, 31, 2)),
        'min_samples_split': randint(2, 11),
        'min_samples_leaf': randint(1, 6),
        'class_weight': [None, 'balanced']
    }

    xgb_param_dist = {
        'n_estimators': randint(100, 500),
        'max_depth': randint(3, 12),
        'learning_rate': uniform(0.01, 0.3),
        'subsample': uniform(0.5, 0.5),
        'colsample_bytree': uniform(0.5, 0.5)
    }

    lgb_param_dist = {
        'n_estimators': randint(100, 500),
        'max_depth': randint(3, 16),
        'learning_rate': uniform(0.01, 0.3),
        'num_leaves': randint(20, 200),
        'subsample': uniform(0.5, 0.5)
    }

    # Helper to run RandomizedSearchCV
    def _run_search(estimator, param_dist, X, y, name):
        print(f"Starting RandomizedSearchCV for {name} (n_iter={n_iter})")
        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=param_dist,
            n_iter=n_iter,
            scoring='f1_weighted',
            cv=cv,
            random_state=random_state,
            n_jobs=-1,
            verbose=1
        )
        search.fit(X, y)
        print(f"Best {name} CV score: {search.best_score_:.4f}")
        print(f"Best {name} params: {search.best_params_}")
        return search.best_estimator_, search

    # Run searches - use training data (already sampled if sampling applied in preprocess)
    # RandomForest
    rf_estimator = RandomForestClassifier(random_state=random_state, n_jobs=-1)
    best_rf, rf_search = _run_search(rf_estimator, rf_param_dist, X_train, y_train, 'RandomForest')

    # XGBoost
    try:
        import xgboost as xgb
        xgb_estimator = xgb.XGBClassifier(use_label_encoder=False, eval_metric='mlogloss', random_state=random_state, n_jobs=-1)
        best_xgb, xgb_search = _run_search(xgb_estimator, xgb_param_dist, X_train, y_train, 'XGBoost')
    except Exception as e:
        print('XGBoost not available or import failed:', e)
        best_xgb, xgb_search = None, None

    # LightGBM
    try:
        import lightgbm as lgb
        lgb_estimator = lgb.LGBMClassifier(random_state=random_state, n_jobs=-1)
        best_lgb, lgb_search = _run_search(lgb_estimator, lgb_param_dist, X_train, y_train, 'LightGBM')
    except Exception as e:
        print('LightGBM not available or import failed:', e)
        best_lgb, lgb_search = None, None

    # Evaluate on holdout test set
    def _eval_model(model, X_t, y_t, name):
        if model is None:
            return None
        y_pred = model.predict(X_t)
        metrics = {
            'accuracy': float(accuracy_score(y_t, y_pred)),
            'precision': float(precision_score(y_t, y_pred, average='weighted', zero_division=0)),
            'recall': float(recall_score(y_t, y_pred, average='weighted', zero_division=0)),
            'f1': float(f1_score(y_t, y_pred, average='weighted', zero_division=0))
        }
        print(f"{name} test F1: {metrics['f1']:.4f}")
        return metrics

    results['random_forest'] = {
        'best_estimator': best_rf,
        'search': rf_search,
        'test_metrics': _eval_model(best_rf, X_test, y_test, 'RandomForest')
    }
    results['xgboost'] = {
        'best_estimator': best_xgb,
        'search': xgb_search,
        'test_metrics': _eval_model(best_xgb, X_test, y_test, 'XGBoost')
    }
    results['lightgbm'] = {
        'best_estimator': best_lgb,
        'search': lgb_search,
        'test_metrics': _eval_model(best_lgb, X_test, y_test, 'LightGBM')
    }

    # Persist best models and search results
    os.makedirs('models/hyperopt', exist_ok=True)
    for name, info in results.items():
        est = info.get('best_estimator')
        search_obj = info.get('search')
        if est is not None:
            joblib.dump(est, f"models/hyperopt/{name}_best.pkl")
        if search_obj is not None:
            with open(f"models/hyperopt/{name}_search.json", 'w') as f:
                json.dump({'best_params': search_obj.best_params_, 'best_score': search_obj.best_score_}, f, indent=2)

    return results

def main():
    parser = argparse.ArgumentParser(
        description='Train and evaluate models for malware detection'
    )
    parser.add_argument('--config',
                       default='configs/model_configs.yaml',
                       help='Model configuration file')
    parser.add_argument('--features',
                       default='data/processed/features.csv',
                       help='Extracted features file')
    parser.add_argument('--labels',
                       default='data/processed/labels.csv',
                       help='Labels file')
    parser.add_argument('--outdir',
                       default='results',
                       help='Output directory for results')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(Path(args.config))
    
    # Load and preprocess data
    features, labels = load_data(Path(args.features), Path(args.labels))
    X_train, X_test, y_train, y_test, scaler = preprocess_data(features, labels, sampling_strategy='smote')
    
    # Train models
    print("Training Random Forest...")
    rf_model = train_random_forest(X_train, y_train, config)
    
    print("Training XGBoost...")
    xgb_model = train_xgboost(X_train, y_train, config)
    
    print("Training LightGBM...")
    lgb_model = train_lightgbm(X_train, y_train, config)
    
    # Train ensemble
    print("Training Ensemble...")
    models = [
        ('rf', rf_model),
        ('xgb', xgb_model),
        ('lgb', lgb_model)
    ]
    ensemble = train_ensemble(models, X_train, y_train)
    
    # Evaluate models
    all_metrics = []
    save_path = Path(args.outdir)
    save_path.mkdir(parents=True, exist_ok=True)
    
    for name, model in [('RandomForest', rf_model),
                       ('XGBoost', xgb_model),
                       ('LightGBM', lgb_model),
                       ('Ensemble', ensemble)]:
        print(f"\nEvaluating {name}...")
        metrics = evaluate_model(model, X_test, y_test, name)
        all_metrics.append(metrics)
        
        # Plot confusion matrix
        plot_confusion_matrix(
            np.array(metrics['confusion_matrix']),
            name,
            save_path
        )
        
        # Plot feature importance (if available)
        if name != 'Ensemble':
            plot_feature_importance(
                model,
                features.columns.tolist(),
                name,
                save_path
            )
    
    # Plot ROC curves
    plot_roc_curves(all_metrics, save_path)
    
    # Save results
    save_results(all_metrics, save_path)
    
    # Print summary
    print("\nResults Summary:")
    for metrics in all_metrics:
        name = metrics['model']
        print(f"\n{name}:")
        print(f"Accuracy:  {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1 Score:  {metrics['f1']:.4f}")
        print(f"AUC:       {metrics['auc']:.4f}")

if __name__ == '__main__':
    main()