class Coach:
    """
    Monitors user behavior and provides interventions to prevent drop-off.
    """
    def __init__(self, active=True):
        self.active = active

    def observe_and_intervene(self, persona, funnel_state, signals):
        """
        Analyzes behavioral signals and decides if an intervention is needed.
        """
        if not self.active:
            return None

        # Example intervention logic
        if funnel_state == "PRODUCT_TARIFF_SELECTION":
            dwell_time = signals.get('dwell_time', 0)
            if dwell_time > 40: # If user dwells for more than 40 seconds
                return self.trigger_intervention("price_reframing", persona, funnel_state)

        if funnel_state == "RECOMMENDATION_FINAL_PRICE":
            # Example: Detects hesitation signals
            if signals.get('hovers_on_cancel', 0) > 2:
                 return self.trigger_intervention("reassurance", persona, funnel_state)

        return None

    def trigger_intervention(self, intervention_type, persona, funnel_state):
        """
        Generates the content for a specific intervention.
        """
        # TODO: Implement a more sophisticated intervention generation
        if intervention_type == "price_reframing":
            message = f"[COACH] Detected: long dwell on price. Intervention: price reframing.\n" \
                      f"[COACH] 'The Optimal tariff costs less than a coffee a day.'"
            print(message)
            return message
        
        if intervention_type == "reassurance":
            message = f"[COACH] Detected: near-abandonment. Intervention: transparency + reassurance.\n" \
                      f"[COACH] 'Your final price is based on your health profile. You can still complete the purchase online right now.'"
            print(message)
            return message

        return None
