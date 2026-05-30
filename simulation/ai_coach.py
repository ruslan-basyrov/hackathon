import pickle
import os
import pandas as pd

class AICoach:
    """
    An AI-powered coach that uses a trained Decision Tree model to decide 
    when and how to intervene based on real-time behavioral signals.
    """
    def __init__(self, active=True):
        self.active = active
        self.model = self._load_model()

    def _load_model(self):
        """Loads the pre-trained decision tree model from disk."""
        model_path = os.path.join(os.path.dirname(__file__), '..', 'coach_model.pkl')
        try:
            with open(model_path, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            print("ERROR: Model file 'coach_model.pkl' not found.")
            print("Please run 'train_tree.py' first to generate the model.")
            return None

    def observe_and_intervene(self, persona, funnel_state, signals):
        """
        Uses the ML model to predict the best intervention.
        """
        if not self.active or self.model is None:
            return None

        # --- Map FunnelState to the numeric step_id used in training ---
        state_to_id = {
            'PRODUCT_TARIFF_SELECTION': 4,
            'RECOMMENDATION_FINAL_PRICE': 7
        }
        step_id = state_to_id.get(funnel_state)
        
        # Only intervene on the steps the model was trained on
        if step_id is None:
            return None

        # --- Prepare the feature vector for prediction ---
        features = pd.DataFrame([{
            "step_id": step_id,
            "dwell_time": signals.get('dwell_time', 0),
            "hovers": signals.get('hovers_on_price', 0) + signals.get('hovers_on_cancel', 0),
            "scrolls": 1 if signals.get('scrolls_back_and_forth') else 0
        }])

        # --- Predict the intervention ---
        prediction = self.model.predict(features)[0]

        if prediction != "none":
            return self.trigger_intervention(prediction, persona, funnel_state)

        return None

    def trigger_intervention(self, intervention_type, persona, funnel_state):
        """
        Generates the content for a specific intervention.
        """
        message = f"[AI COACH] Predicted: '{intervention_type}' for {persona.name} at step {funnel_state}.\n"
        
        if intervention_type == "price_reframing":
            message += f"[AI COACH] 'The Optimal tariff costs less than a coffee a day.'"
        elif intervention_type == "reassurance":
            message += f"[AI COACH] 'Your final price is based on your health profile. You can still complete the purchase online right now.'"
        
        print(message)
        return message
