import random

class Persona:
    """
    Represents a user persona, making decisions based on its personality traits and probabilities.
    The decision logic is a Finite State Machine (FSM) driven by the persona's attributes.
    """
    def __init__(self, segment_id, name, segment_data):
        self.segment_id = segment_id
        self.name = name
        self.segment_data = segment_data
        self.instance_attributes = {}
        self.llm_prompt = ""

    def decide(self, funnel_state):
        """
        Makes a decision based on the current state of the funnel using probabilistic logic.
        This is the core of the bot's "decision tree".
        """
        print(f"[{self.name}] is at state {funnel_state} and is making a decision...")

        # Default action and signals
        action = "PROCEED"
        signals = {'dwell_time': random.uniform(2, 10)}

        # --- Step 4: Initial Price Display ---
        if funnel_state == 'PRODUCT_TARIFF_SELECTION':
            # Get the persona's sensitivity to price from the main segment data
            price_sensitivity = self.segment_data.get('decision_drivers_pct', {}).get('price_performance_ratio', 50) / 100.0
            cheapest_focus = self.segment_data.get('decision_drivers_pct', {}).get('always_picks_cheapest', 20) / 100.0

            # The higher the price sensitivity, the longer they dwell and the more likely they are to hesitate
            signals['dwell_time'] = random.uniform(5, 60) * (1 + price_sensitivity)

            # Probabilistic decision
            hesitation_prob = price_sensitivity * 0.5  # Base hesitation probability
            abandon_prob = cheapest_focus * 0.3 # If they always pick the cheapest, they might just leave
            proceed_prob = 1 - hesitation_prob - abandon_prob

            action = random.choices(
                population=["HESITATE", "ABANDON", "PROCEED"],
                weights=[hesitation_prob, abandon_prob, proceed_prob],
                k=1
            )[0]
            
            if action == "HESITATE":
                signals['hovers_on_price'] = random.randint(3, 10)
                signals['scrolls_back_and_forth'] = True
            
            print(f"    - Price Sensitivity: {price_sensitivity:.2f}, Action: {action}")


        # --- Step 7: Final Price Display ---
        elif funnel_state == 'RECOMMENDATION_FINAL_PRICE':
            # This step has a high drop-off. Let's model it.
            # Let's assume the final price is 15% higher than the estimate
            price_gap_sensitivity = self.segment_data.get('pain_points', []).count("Opaque prices or terms") > 0
            
            abandon_prob = 0.1
            if price_gap_sensitivity:
                abandon_prob = 0.78 # Use the documented drop-off rate for sensitive personas

            if random.random() < abandon_prob:
                action = "ABANDON"
                signals['hovers_on_cancel'] = random.randint(1, 5)
            else:
                action = "PROCEED"

            print(f"    - Price Gap Sensitive: {price_gap_sensitivity}, Action: {action}")

        return action, signals

    def __str__(self):
        return f"Persona(name={self.name}, segment={self.segment_id})"
