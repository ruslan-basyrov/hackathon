from bots.persona_factory import PersonaFactory

def test_persona_generation():
    """
    Tests the generation of unique persona instances and their LLM prompts.
    """
    personas_json_path = 'tracks/insurance-uniqa/personas.json'
    factory = PersonaFactory(personas_json_path)
    
    print("--- Generating Persona Instances and LLM Prompts ---")
    
    segments = factory.get_available_segments()
    
    for segment_id in segments:
        print(f"\n\n==================== GENERATING FOR: {segment_id.upper()} ====================")
        persona = factory.create_persona(segment_id)
        
        print(f"\n--- Persona Instance Attributes for {persona.name} ---")
        for key, value in persona.instance_attributes.items():
            print(f"{key}: {value}")
            
        print(f"\n--- Generated LLM Prompt for {persona.name} ---")
        print(persona.llm_prompt)
        print("======================================================================")

if __name__ == "__main__":
    test_persona_generation()
