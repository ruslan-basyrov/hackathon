import json
import random

class PersonaFactory:
    """
    Creates Persona instances from a JSON definition file,
    sampling probabilities to generate specific, unique instances.
    """
    def __init__(self, personas_path):
        with open(personas_path, 'r', encoding='utf-8') as f:
            self.personas_data = json.load(f)

    def _sample_from_dict(self, pct_dict):
        """
        Takes a dictionary of { "option": percentage } and returns one option
        based on the probability distribution.
        Ignores keys that are not numeric distributions (like 'matura_significantly_above_average').
        """
        # Filter out non-numeric values
        valid_options = {k: v for k, v in pct_dict.items() if isinstance(v, (int, float))}
        if not valid_options:
            return None
            
        options = list(valid_options.keys())
        weights = list(valid_options.values())
        
        return random.choices(options, weights=weights, k=1)[0]

    def _generate_instance_attributes(self, segment_data):
        """
        Generates specific attributes for a persona instance by sampling from the segment data.
        """
        demo = segment_data.get('demographics', {})
        
        # Sample demographics
        age_group = self._sample_from_dict(demo.get('age_distribution_pct', {}))
        gender_options = {'female': demo.get('female_pct', 0), 'male': demo.get('male_pct', 0), 'diverse': demo.get('diverse_pct', 0)}
        gender = self._sample_from_dict(gender_options)
        
        education = self._sample_from_dict(demo.get('education', {}))
        urbanity = self._sample_from_dict(demo.get('urbanity', {}))
        region = self._sample_from_dict(demo.get('regional_distribution_pct', {}))
        household = self._sample_from_dict(demo.get('household', {}))
        employment = self._sample_from_dict(demo.get('employment', {}))

        # Sample textual traits
        behavior = random.sample(segment_data.get('behavior_and_attitudes', []), min(2, len(segment_data.get('behavior_and_attitudes', []))))
        needs = random.sample(segment_data.get('needs', []), min(2, len(segment_data.get('needs', []))))
        pain_points = random.sample(segment_data.get('pain_points', []), min(2, len(segment_data.get('pain_points', []))))

        # Determine primary decision driver
        primary_driver = self._sample_from_dict(segment_data.get('decision_drivers_pct', {}))

        return {
            "age_group": age_group,
            "gender": gender,
            "education": education,
            "urbanity": urbanity,
            "region": region,
            "household": household,
            "employment": employment,
            "behavior_traits": behavior,
            "needs": needs,
            "pain_points": pain_points,
            "primary_decision_driver": primary_driver
        }

    def _generate_llm_prompt(self, segment_data, instance_attrs):
        """
        Generates a system prompt to feed to an LLM representing this persona.
        """
        archetype = segment_data.get('persona_archetype', {})
        
        prompt = (
            f"You are {archetype.get('name')}, simulating a user looking for health insurance online.\n"
            f"Segment: {segment_data.get('name_full')} ({segment_data.get('name_short')})\n"
            f"Your typical quote: '{archetype.get('typical_quote')}'\n\n"
            
            f"--- Your Demographics ---\n"
            f"Age Group: {instance_attrs['age_group']}\n"
            f"Gender: {instance_attrs['gender']}\n"
            f"Education: {'With Matura' if instance_attrs['education'] == 'with_matura_pct' else 'Without Matura'}\n"
            f"Living in: {instance_attrs['region']} ({instance_attrs['urbanity'].replace('_pct', '')})\n"
            f"Household: {instance_attrs['household'].replace('_pct', '')}\n"
            f"Employment: {instance_attrs['employment'].replace('_pct', '')}\n\n"
            
            f"--- Your Personality & Attitudes ---\n"
            f"Behaviors:\n- " + "\n- ".join(instance_attrs['behavior_traits']) + "\n"
            f"Needs:\n- " + "\n- ".join(instance_attrs['needs']) + "\n"
            f"Pain Points:\n- " + "\n- ".join(instance_attrs['pain_points']) + "\n"
            f"Primary Decision Driver: {instance_attrs['primary_decision_driver'].replace('_', ' ').title()}\n\n"
            
            f"--- Instructions ---\n"
            f"When presented with options in an insurance funnel, make decisions that align with these traits. "
            f"If you are highly price sensitive, you might hesitate when seeing high prices. "
            f"If you value personal advisory, you might drop off if forced to do everything online without help."
        )
        return prompt

    def create_persona(self, segment_id):
        """
        Creates a single persona based on the segment ID, generating unique attributes and a prompt.
        """
        segment_data = self.personas_data['personas'].get(segment_id)
        if not segment_data:
            raise ValueError(f"Segment '{segment_id}' not found in personas data.")

        persona_name = segment_data['persona_archetype']['name']
        
        # 1. Generate unique probabilistic attributes
        instance_attrs = self._generate_instance_attributes(segment_data)
        
        # 2. Generate LLM prompt based on the base segment data and the unique attributes
        llm_prompt = self._generate_llm_prompt(segment_data, instance_attrs)

        # 3. Import Persona here to avoid circular imports if any, or assume it's correctly structured
        from bots.persona import Persona
        
        persona = Persona(segment_id, persona_name, segment_data)
        # Attach the generated instance data to the persona
        persona.instance_attributes = instance_attrs
        persona.llm_prompt = llm_prompt
        
        return persona

    def get_available_segments(self):
        """Returns a list of available persona segment IDs."""
        return list(self.personas_data['personas'].keys())