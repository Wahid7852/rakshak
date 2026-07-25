# Defines source model workflow for train.
#!/usr/bin/env python3
"""
Advanced malware classification using multiple models and ensemble methods.

Supported Models:
1. Random Forest (baseline)
2. XGBoost (gradient boosting)
3. LightGBM (gradient boosting)
4. Neural Network (MLP)
5. Ensemble (voting classifier)

Features:
- Automatic model selection
- Hyperparameter optimization
- Cross-validation
- Feature importance analysis
- Model comparison
"""

import os, sys, argparse, sys, json
from pathlib import Path
from typing import Dict, Any, Tuple, List

import joblib, numpy as np, pandas as pd, matplotlib.pyplot as plt, seaborn as sns
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, 
    roc_curve, auc, precision_recall_curve
)
from sklearn.model_selection import (
    train_test_split, GridSearchCV, 
    cross_val_score, StratifiedKFold
)
from sklearn.preprocessing import StandardScaler, LabelEncoder
import xgboost as xgb, lightgbm as lgb

# Add project root to path

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)

from src.utils.helpers import strip_encrypted_suffix

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Default paths
DEFAULT_PATHS = {
    'features': PROJECT_ROOT / 'data' / 'processed' / 'features.csv',
    'labels': PROJECT_ROOT / 'data' / 'processed' / 'labels.csv',
    'models': PROJECT_ROOT / 'models',
    'results': PROJECT_ROOT / 'results'
}

# Model configurations
MODEL_CONFIGS = {
    'rf': {
        'class': RandomForestClassifier,
        'params': {
            'n_estimators': [100, 200, 300, 500],
            'max_depth': [None, 10, 20, 30, 50],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['sqrt', 'log2'],
            'bootstrap': [True, False],
            'class_weight': ['balanced', 'balanced_subsample', None],
            'random_state': [42],
            'n_jobs': [-1],
            'verbose': [0]
        }
    },
    'xgb': {
        'class': xgb.XGBClassifier,
        'params': {
            'n_estimators': [100, 200, 300, 500],
            'max_depth': [3, 6, 9],
            'learning_rate': [0.01, 0.05, 0.1],
            'min_child_weight': [1, 3, 5],
            'gamma': [0, 0.1, 0.2],
            'subsample': [0.8, 0.9],
            'colsample_bytree': [0.8, 0.9],
            'scale_pos_weight': [1, 3, 5],
            'reg_alpha': [0, 0.1, 0.5],
            'reg_lambda': [1, 1.5, 2],
            'random_state': [42],
            'n_jobs': [-1],
            'verbosity': [0]
        }
    },
    'lgb': {
        'class': lgb.LGBMClassifier,
        'params': {
            'n_estimators': [100, 200, 300, 500],
            'num_leaves': [7, 15, 31],
            'learning_rate': [0.01, 0.05, 0.1],
            'min_child_samples': [5, 10, 20],
            'min_child_weight': [0.001, 0.01, 0.1],
            'subsample': [0.8, 0.9],
            'colsample_bytree': [0.8, 0.9],
            'reg_alpha': [0, 0.1, 0.5],
            'reg_lambda': [0, 1.0, 2.0],
            'min_split_gain': [0.0, 0.1],
            'class_weight': ['balanced'],
            'random_state': [42],
            'n_jobs': [-1],
            'verbose': [-1]
        }
    },
    'nn': {
        'class': MLPClassifier,
        'params': {
            'hidden_layer_sizes': [(100,), (100, 50), (100, 50, 25), (200, 100, 50)],
            'activation': ['relu', 'tanh'],
            'solver': ['adam'],
            'alpha': [0.0001, 0.001, 0.01],
            'batch_size': ['auto'],
            'learning_rate': ['adaptive'],
            'learning_rate_init': [0.001, 0.01],
            'max_iter': [1000],
            'early_stopping': [True],
            'validation_fraction': [0.1],
            'n_iter_no_change': [10],
            'random_state': [42],
            'verbose': [0]
        }
    }
}

def optimize_model(model_name: str, X: pd.DataFrame, y: pd.Series,
                    n_folds: int = 5) -> Tuple[Any, Dict[str, Any]]:
    """Optimize hyperparameters for a specific model using cross-validation.
    
    Args:
        model_name: Name of the model to optimize
        X: Feature matrix
        y: Target labels
        n_folds: Number of cross-validation folds
        
    Returns:
        Tuple containing:
        - Best model instance after hyperparameter optimization
        - Dictionary with optimization results
        
    Notes:
        - Uses stratified k-fold cross-validation
        - Optimizes for weighted F1-score to handle class imbalance
        - Includes best parameters, scores, and detailed CV results
    """
    config = MODEL_CONFIGS[model_name]
    clf = config['class']()
    
    # Set up stratified k-fold cross-validation
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    
    # Configure grid search with multiple scoring metrics
    grid_search = GridSearchCV(
        estimator=clf,
        param_grid=config['params'],
        cv=cv,
        scoring={
            'f1': 'f1_weighted',
            'precision': 'precision_weighted',
            'recall': 'recall_weighted',
            'auc': 'roc_auc_ovr_weighted'
        },
        refit='f1',  # Use F1 score to select best model
        n_jobs=-1,
        verbose=1,
        return_train_score=True
    )
    
    # Fit the grid search
    grid_search.fit(X, y)
    
    # Extract cross-validation results
    cv_results = pd.DataFrame(grid_search.cv_results_)
    
    # Calculate feature importance if available
    feature_importance = None
    if hasattr(grid_search.best_estimator_, 'feature_importances_'):
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': grid_search.best_estimator_.feature_importances_
        }).sort_values('importance', ascending=False)
    
    return grid_search.best_estimator_, {
        'best_params': grid_search.best_params_,
        'best_score': {
            'f1': grid_search.cv_results_['mean_test_f1'][grid_search.best_index_],
            'precision': grid_search.cv_results_['mean_test_precision'][grid_search.best_index_],
            'recall': grid_search.cv_results_['mean_test_recall'][grid_search.best_index_],
            'auc': grid_search.cv_results_['mean_test_auc'][grid_search.best_index_]
        },
        'cv_results': cv_results.to_dict(orient='records'),
        'feature_importance': feature_importance.to_dict(orient='records')
        if feature_importance is not None else None
    }

def create_ensemble(models: Dict[str, Any]) -> VotingClassifier:
    """Create a voting ensemble from multiple models."""
    estimators = [(name, model) for name, model in models.items()]
    return VotingClassifier(estimators=estimators, voting='soft')

def evaluate_model(model: Any, X: pd.DataFrame, y: pd.Series, 
                  feature_names: List[str], label_encoder: LabelEncoder = None) -> Dict[str, Any]:
    """Perform comprehensive model evaluation with multiple metrics.
    
    Args:
        model: Trained model instance
        X: Feature matrix
        y: True labels
        feature_names: List of feature names
        label_encoder: Optional label encoder for class names
        
    Returns:
        Dictionary containing evaluation metrics:
        - Cross-validation scores
        - Feature importance
        - ROC curves
        - Precision-Recall curves
        - Confusion matrix
        - Classification report
        - Feature permutation importance
        
    Note:
        Uses stratified k-fold CV and calculates class-wise metrics
    """
    # Cross-validation with multiple metrics
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    metrics = ['accuracy', 'precision_weighted', 'recall_weighted', 'f1_weighted']
    cv_results = {}
    
    for metric in metrics:
        scores = cross_val_score(model, X, y, cv=cv, scoring=metric)
        cv_results[metric] = {
            'mean': float(scores.mean()),
            'std': float(scores.std()),
            'scores': scores.tolist()
        }
    
    # Feature importance from model (if available)
    importance = None
    if hasattr(model, 'feature_importances_'):
        importance = pd.DataFrame({
            'feature': feature_names,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
    
    # Predictions on validation set
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)
    
    # Get original class names
    classes = label_encoder.inverse_transform(model.classes_) if label_encoder else model.classes_
    
    # ROC curves per class
    roc_curves = {}
    pr_curves = {}
    
    for i, class_name in enumerate(classes):
        # ROC curve
        fpr, tpr, _ = roc_curve(y == model.classes_[i], y_prob[:, i])
        roc_auc = auc(fpr, tpr)
        roc_curves[class_name] = {
            'fpr': fpr.tolist(),
            'tpr': tpr.tolist(),
            'auc': float(roc_auc)
        }
        
        # Precision-Recall curve
        precision, recall, _ = precision_recall_curve(y == model.classes_[i], y_prob[:, i])
        pr_auc = auc(recall, precision)
        pr_curves[class_name] = {
            'precision': precision.tolist(),
            'recall': recall.tolist(),
            'auc': float(pr_auc)
        }
    
    # Calculate permutation feature importance
    from sklearn.inspection import permutation_importance
    r = permutation_importance(
        model, X, y,
        n_repeats=10,
        random_state=42,
        n_jobs=-1
    )
    
    perm_importance = pd.DataFrame({
        'feature': feature_names,
        'importance_mean': r.importances_mean,
        'importance_std': r.importances_std
    }).sort_values('importance_mean', ascending=False)
    
    # Generate classification report with additional metrics
    clf_report = classification_report(y, y_pred, output_dict=True)
    
    # Add additional per-class metrics
    for class_name in classes:
        class_name_str = str(class_name)  # Convert to string for dict key
        if class_name_str in clf_report:
            idx = label_encoder.transform([class_name])[0] if label_encoder else class_name
            class_probs = y_prob[:, model.classes_.tolist().index(idx)]
            clf_report[class_name_str].update({
                'roc_auc': roc_curves[class_name]['auc'],
                'pr_auc': pr_curves[class_name]['auc']
            })
    
    return {
        'cv_scores': cv_results,
        'feature_importance': importance.to_dict(orient='records') if importance is not None else None,
        'permutation_importance': perm_importance.to_dict(orient='records'),
        'confusion_matrix': confusion_matrix(y, y_pred, normalize='true').tolist(),  # Normalized
        'classification_report': clf_report,
        'roc_curves': roc_curves,
        'pr_curves': pr_curves,
        'predictions': {
            'y_true': y.tolist(),
            'y_pred': y_pred.tolist(),
            'y_prob': y_prob.tolist()
        }
    }

def plot_model_comparison(results: Dict[str, Dict[str, Any]], output_dir: Path):
    """Generate comprehensive comparison plots for multiple models.
    
    Args:
        results: Dictionary of evaluation results for each model
        output_dir: Directory to save plot files
        
    Generates:
        - Model performance comparison (multiple metrics)
        - ROC curves comparison
        - Precision-Recall curves comparison
        - Confusion matrices
        - Feature importance plots
        - Learning curves
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up the plotting style
    plt.style.use('seaborn')
    sns.set_palette('husl')
    
    # Model performance comparison - multiple metrics
    metrics = ['accuracy', 'precision_weighted', 'recall_weighted', 'f1_weighted']
    plt.figure(figsize=(15, 8))
    
    # Create a subplot for each metric
    for i, metric in enumerate(metrics, 1):
        plt.subplot(2, 2, i)
        scores = {name: res['cv_scores'][metric]['mean'] for name, res in results.items()}
        std_devs = {name: res['cv_scores'][metric]['std'] for name, res in results.items()}
        
        # Create bar plot with error bars
        ax = sns.barplot(x=list(scores.keys()), y=list(scores.values()), 
                        yerr=list(std_devs.values()), capsize=5)
        
        plt.title(f'{metric.replace("_", " ").title()}', fontsize=10)
        plt.xticks(rotation=45)
        plt.ylabel('Score', fontsize=9)
        
        # Add value labels
        for i, v in enumerate(scores.values()):
            ax.text(i, v + 0.01, f'{v:.3f}', ha='center', fontsize=8)
            
    plt.tight_layout()
    plt.savefig(output_dir / 'model_comparison_metrics.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # ROC curves comparison - one plot per class
    classes = next(iter(results.values()))['roc_curves'].keys()
    num_classes = len(classes)
    plt.figure(figsize=(15, 5 * ((num_classes + 2) // 3)))
    
    for i, class_name in enumerate(classes, 1):
        plt.subplot((num_classes + 2) // 3, 3, i)
        
        for model_name, result in results.items():
            roc_data = result['roc_curves'][class_name]
            plt.plot(roc_data['fpr'], roc_data['tpr'],
                    label=f'{model_name} (AUC={roc_data["auc"]:.3f})',
                    linewidth=2)
        
        plt.plot([0, 1], [0, 1], 'k--', label='Random')
        plt.xlabel('False Positive Rate', fontsize=9)
        plt.ylabel('True Positive Rate', fontsize=9)
        plt.title(f'ROC Curve - {class_name}', fontsize=10)
        plt.legend(fontsize=8)
        plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'roc_curves.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Precision-Recall curves comparison - one plot per class
    plt.figure(figsize=(15, 5 * ((num_classes + 2) // 3)))
    
    for i, class_name in enumerate(classes, 1):
        plt.subplot((num_classes + 2) // 3, 3, i)
        
        for model_name, result in results.items():
            pr_data = result['pr_curves'][class_name]
            plt.plot(pr_data['recall'], pr_data['precision'],
                    label=f'{model_name} (AUC={pr_data["auc"]:.3f})',
                    linewidth=2)
        
        plt.xlabel('Recall', fontsize=9)
        plt.ylabel('Precision', fontsize=9)
        plt.title(f'Precision-Recall Curve - {class_name}', fontsize=10)
        plt.legend(fontsize=8)
        plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'pr_curves.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Plot confusion matrices for each model
    for model_name, result in results.items():
        plt.figure(figsize=(12, 10))
        cm = np.array(result['confusion_matrix'])
        
        # Create heatmap with improved formatting
        sns.heatmap(cm, annot=True, fmt='.2%', cmap='Blues',
                   xticklabels=list(result['classification_report'].keys())[:-3],
                   yticklabels=list(result['classification_report'].keys())[:-3])
        
        plt.title(f'Confusion Matrix - {model_name.upper()}', fontsize=12, pad=20)
        plt.ylabel('True Label', fontsize=10)
        plt.xlabel('Predicted Label', fontsize=10)
        
        plt.tight_layout()
        plt.savefig(output_dir / f'confusion_matrix_{model_name}.png', dpi=300, bbox_inches='tight')
        plt.close()
        
    # Feature importance comparison
    for model_name, result in results.items():
        if result['feature_importance'] or result['permutation_importance']:
            plt.figure(figsize=(15, 10))
            
            # Model-based importance
            if result['feature_importance']:
                plt.subplot(1, 2, 1)
                feat_imp = pd.DataFrame(result['feature_importance'])
                feat_imp = feat_imp.sort_values('importance', ascending=True).tail(20)
                
                sns.barplot(x='importance', y='feature', data=feat_imp)
                plt.title('Model Feature Importance', fontsize=10)
                plt.xlabel('Importance Score', fontsize=9)
            
            # Permutation importance
            if result['permutation_importance']:
                plt.subplot(1, 2, 2)
                perm_imp = pd.DataFrame(result['permutation_importance'])
                perm_imp = perm_imp.sort_values('importance_mean', ascending=True).tail(20)
                
                sns.barplot(x='importance_mean', y='feature', data=perm_imp)
                plt.title('Permutation Feature Importance', fontsize=10)
                plt.xlabel('Mean Importance Score', fontsize=9)
            
            plt.suptitle(f'Feature Importance Analysis - {model_name.upper()}', fontsize=12, y=1.02)
            plt.tight_layout()
            plt.savefig(output_dir / f'feature_importance_{model_name}.png', dpi=300, bbox_inches='tight')
            plt.close()

def main():
    parser = argparse.ArgumentParser(description="Train and compare multiple models for malware detection.")
    parser.add_argument("--features", default=str(DEFAULT_PATHS['features']), help="Input features CSV file")
    parser.add_argument("--labels", default=str(DEFAULT_PATHS['labels']), help="Input labels CSV file")
    parser.add_argument("--models-dir", default=str(DEFAULT_PATHS['models']), help="Output directory for models")
    parser.add_argument("--results-dir", default=str(DEFAULT_PATHS['results']), help="Directory for evaluation results")
    parser.add_argument("--models", nargs='+', choices=['rf', 'xgb', 'lgb', 'nn', 'ensemble'],
                      default=['rf', 'xgb', 'lgb'], help="Models to train")
    args = parser.parse_args()

    # Load and prepare data
    print("Loading data...")
    feat_path = Path(args.features)
    if not feat_path.exists():
        print("features.csv not found. Run features.py first.", file=sys.stderr)
        sys.exit(1)

    # Load TLS features
    df = pd.read_csv(feat_path)
    df["file"] = df["file"].astype(str)
    df["orig_file"] = df["file"].apply(strip_encrypted_suffix)
    
    # Load CNN features if available
    cnn_features_path = Path("cnn_features.csv")
    if cnn_features_path.exists():
        print("Loading CNN features...")
        cnn_df = pd.read_csv(cnn_features_path)
        cnn_df["file"] = cnn_df["file"].astype(str)
        # Merge CNN features
        df = df.merge(cnn_df, on="file", how="left")
        print(f"Combined feature count: {len(df.columns)}")

    # Load labels
    labels_path = Path(args.labels)
    if labels_path.exists():
        labdf = pd.read_csv(labels_path)
        labdf = labdf[["file", "family"]].copy()
        labdf["file"] = labdf["file"].astype(str)
        df = df.merge(labdf.rename(columns={"file": "orig_file"}), on="orig_file", how="left")
        df["family"] = df["family"].fillna("unknown")
    else:
        print("labels.csv not found. Assigning 'unknown' labels.")
        df["family"] = "unknown"

    # Prepare features
    X = df.select_dtypes(include=[np.number]).fillna(0.0)
    feature_names = X.columns.tolist()
    
    # Scale features
    scaler = StandardScaler()
    X = pd.DataFrame(scaler.fit_transform(X), columns=feature_names)

    # Prepare labels
    y = df["family"].astype(str).fillna("unknown")
    
    # Encode categorical labels to numerical values
    from sklearn.preprocessing import LabelEncoder
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(y)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # Train and evaluate models
    trained_models = {}
    results = {}
    
    for model_name in args.models:
        if model_name == 'ensemble' and len(trained_models) < 2:
            print("Skipping ensemble - need at least 2 models first")
            continue
            
        print(f"\nTraining {model_name.upper()}...")
        
        if model_name == 'ensemble':
            model = create_ensemble(trained_models)
            model.fit(X_train, y_train)
        else:
            model, opt_results = optimize_model(model_name, X_train, y_train)
            trained_models[model_name] = model
            
        # Evaluate model
        print(f"Evaluating {model_name.upper()}...")
        results[model_name] = evaluate_model(model, X_test, y_test, feature_names, label_encoder)
        
        # Save model
        model_path = Path(args.models_dir) / f"{model_name}.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            'model': model,
            'feature_names': feature_names,
            'scaler': scaler,
            'label_encoder': label_encoder,
            'classes': label_encoder.inverse_transform(model.classes_).tolist()
        }, model_path)
        
        # Print summary
        print(f"\n{model_name.upper()} Performance:")
        print(f"F1 Score (mean ± std): {results[model_name]['cv_scores']['mean']:.3f} ± {results[model_name]['cv_scores']['std']:.3f}")

    # Generate comparison plots and save results
    results_dir = Path(args.results_dir)
    plot_model_comparison(results, results_dir)
    
    with open(results_dir / 'evaluation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved models to {args.models_dir}")
    print(f"Saved evaluation results to {args.results_dir}")
    
    # Print best model
    best_model = max(results.items(), key=lambda x: x[1]['cv_scores']['mean'])
    print(f"\nBest performing model: {best_model[0].upper()}")
    print(f"F1 Score: {best_model[1]['cv_scores']['mean']:.3f} ± {best_model[1]['cv_scores']['std']:.3f}")

if __name__ == "__main__":
    main()