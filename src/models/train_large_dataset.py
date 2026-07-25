# Defines source model workflow for train large dataset.
#!/usr/bin/env python3
"""
Train models on the large test dataset (10,873 samples, 9 classes)
"""

import os, sys, pandas as pd, numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import xgboost as xgb, lightgbm as lgb, joblib, json

def load_large_dataset():
    """Load the large test dataset and labels."""
    print("Loading large dataset...")
    
    # Load features
    features_path = "data/processed/large_test_features.csv"
    features_df = pd.read_csv(features_path)
    print(f"Loaded features: {features_df.shape}")
    
    # Load labels
    labels_path = "data/processed/large_test_labels.csv"
    labels_df = pd.read_csv(labels_path)
    print(f"Loaded labels: {labels_df.shape}")
    
    # Ensure we have matching samples
    n_features = len(features_df)
    n_labels = len(labels_df)
    min_samples = min(n_features, n_labels)
    
    print(f"Using {min_samples} samples (features: {n_features}, labels: {n_labels})")
    
    # Take the minimum number of samples to ensure alignment
    X = features_df.iloc[:min_samples]
    y = labels_df.iloc[:min_samples]['family']
    
    return X, y

def preprocess_data(X, y):
    """Preprocess the data for training."""
    print("Preprocessing data...")
    
    # Handle missing values
    X_clean = X.fillna(0)
    
    # Remove any non-numeric columns that might cause issues
    numeric_columns = X_clean.select_dtypes(include=[np.number]).columns
    X_numeric = X_clean[numeric_columns]
    
    print(f"Using {len(numeric_columns)} numeric features")
    
    # Encode labels
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    
    print(f"Classes: {label_encoder.classes_}")
    print(f"Class distribution: {pd.Series(y_encoded).value_counts().sort_index().to_dict()}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_numeric, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print(f"Training set: {X_train_scaled.shape}")
    print(f"Test set: {X_test_scaled.shape}")
    
    return X_train_scaled, X_test_scaled, y_train, y_test, scaler, label_encoder

def train_random_forest(X_train, X_test, y_train, y_test):
    """Train Random Forest model."""
    print("\n=== Training Random Forest ===")
    
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=None,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Random Forest Accuracy: {accuracy:.4f}")
    
    # Save model
    os.makedirs("models/random_forest", exist_ok=True)
    joblib.dump(rf, "models/random_forest/large_dataset_model.pkl")
    
    return rf, y_pred

def train_xgboost(X_train, X_test, y_train, y_test):
    """Train XGBoost model."""
    print("\n=== Training XGBoost ===")
    
    xgb_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1
    )
    
    xgb_model.fit(X_train, y_train)
    y_pred = xgb_model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"XGBoost Accuracy: {accuracy:.4f}")
    
    # Save model
    os.makedirs("models/xgboost", exist_ok=True)
    joblib.dump(xgb_model, "models/xgboost/large_dataset_model.pkl")
    
    return xgb_model, y_pred

def train_lightgbm(X_train, X_test, y_train, y_test):
    """Train LightGBM model."""
    print("\n=== Training LightGBM ===")
    
    lgb_model = lgb.LGBMClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1,
        verbose=-1
    )
    
    lgb_model.fit(X_train, y_train)
    y_pred = lgb_model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"LightGBM Accuracy: {accuracy:.4f}")
    
    # Save model
    os.makedirs("models/lightgbm", exist_ok=True)
    joblib.dump(lgb_model, "models/lightgbm/large_dataset_model.pkl")
    
    return lgb_model, y_pred

def train_ensemble(rf_model, xgb_model, lgb_model, X_train, X_test, y_train, y_test):
    """Train ensemble model."""
    print("\n=== Training Ensemble ===")
    
    ensemble = VotingClassifier(
        estimators=[
            ('rf', rf_model),
            ('xgb', xgb_model),
            ('lgb', lgb_model)
        ],
        voting='hard'
    )
    
    ensemble.fit(X_train, y_train)
    y_pred = ensemble.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Ensemble Accuracy: {accuracy:.4f}")
    
    # Save model
    os.makedirs("models/ensemble", exist_ok=True)
    joblib.dump(ensemble, "models/ensemble/large_dataset_model.pkl")
    
    return ensemble, y_pred

def save_results(results, label_encoder):
    """Save training results."""
    print("\n=== Saving Results ===")
    
    # Convert results to serializable format
    serializable_results = {}
    for model_name, result in results.items():
        serializable_results[model_name] = {
            'accuracy': float(result['accuracy']),
            'classification_report': result['classification_report']
        }
    
    # Add class information
    serializable_results['classes'] = label_encoder.classes_.tolist()
    serializable_results['dataset_info'] = {
        'samples': 10873,
        'features': 1804,
        'classes': 9,
        'type': 'large_dataset_multiclass'
    }
    
    # Save to file
    with open("results/large_dataset_results.json", "w") as f:
        json.dump(serializable_results, f, indent=2)
    
    print("Results saved to results/large_dataset_results.json")

def main():
    """Main training function."""
    print("=== Large Dataset Training (Iteration #2) ===")
    print("Dataset: 10,873 samples, 9 malware families")
    
    # Load data
    X, y = load_large_dataset()
    
    # Preprocess
    X_train, X_test, y_train, y_test, scaler, label_encoder = preprocess_data(X, y)
    
    # Train models
    results = {}
    
    # Random Forest
    rf_model, rf_pred = train_random_forest(X_train, X_test, y_train, y_test)
    results['random_forest'] = {
        'accuracy': accuracy_score(y_test, rf_pred),
        'classification_report': classification_report(y_test, rf_pred, output_dict=True)
    }
    
    # XGBoost
    xgb_model, xgb_pred = train_xgboost(X_train, X_test, y_train, y_test)
    results['xgboost'] = {
        'accuracy': accuracy_score(y_test, xgb_pred),
        'classification_report': classification_report(y_test, xgb_pred, output_dict=True)
    }
    
    # LightGBM
    lgb_model, lgb_pred = train_lightgbm(X_train, X_test, y_train, y_test)
    results['lightgbm'] = {
        'accuracy': accuracy_score(y_test, lgb_pred),
        'classification_report': classification_report(y_test, lgb_pred, output_dict=True)
    }
    
    # Ensemble
    ensemble_model, ensemble_pred = train_ensemble(rf_model, xgb_model, lgb_model, X_train, X_test, y_train, y_test)
    results['ensemble'] = {
        'accuracy': accuracy_score(y_test, ensemble_pred),
        'classification_report': classification_report(y_test, ensemble_pred, output_dict=True)
    }
    
    # Save preprocessing objects
    joblib.dump(scaler, "models/scaler_large_dataset.pkl")
    joblib.dump(label_encoder, "models/label_encoder_large_dataset.pkl")
    
    # Print summary
    print("\n=== Training Summary ===")
    for model_name, result in results.items():
        print(f"{model_name.upper()}: {result['accuracy']:.4f}")
    
    # Save results
    os.makedirs("results", exist_ok=True)
    save_results(results, label_encoder)
    
    print("\n=== Training Complete ===")
    return results

if __name__ == "__main__":
    results = main()