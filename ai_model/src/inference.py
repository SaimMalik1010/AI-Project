import joblib
import os

def load_model(filename):
    model_path = os.path.join('models', filename)
    if os.path.exists(model_path):
        return joblib.load(model_path)
    return None

def run_inference(model, data):
    """
    Standardized function to return a prediction.
    """
    if model is None:
        return {"error": "No model loaded"}
    
    prediction = model.predict(data)
    # Check if the model supports probability
    if hasattr(model, "predict_proba"):
        confidence = model.predict_proba(data)
        return {"result": prediction[0], "confidence": np.max(confidence)}
    
    return {"result": prediction[0]}