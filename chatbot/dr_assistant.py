"""
dr_assistant.py — AI Medical Chatbot Assistant
Clinical Knowledge-Base & Conversational Q&A system for Diabetic Retinopathy.
"""

def answer_medical_query(query_text):
    """
    Answers clinical queries regarding Diabetic Retinopathy.
    """
    query = query_text.lower().strip()

    if "what is" in query or "definition" in query or "explain diabetic retinopathy" in query:
        return (
            "**Diabetic Retinopathy (DR)** is a diabetes-related eye complication caused by damage to the small blood vessels of the light-sensitive retina at the back of the eye. "
            "Over time, high blood sugar levels can weaken or block these microvessels, leading to fluid leakage, swelling, or abnormal vessel growth (neovascularization)."
        )

    elif "cause" in query or "why" in query or "risk factor" in query:
        return (
            "**Primary Causes & Risk Factors:**\n"
            "1. **Chronic Hyperglycemia:** Prolonged elevated blood glucose levels.\n"
            "2. **Duration of Diabetes:** Longer duration increases risk.\n"
            "3. **Hypertension:** Uncontrolled high blood pressure accelerates microvascular damage.\n"
            "4. **High Cholesterol / Dyslipidemia:** Contributes to lipid exudate deposits in the retina.\n"
            "5. **Smoking & Renal Disease:** Further compromises vessel integrity."
        )

    elif "symptom" in query or "sign" in query or "vision" in query:
        return (
            "**Common Symptoms of Diabetic Retinopathy:**\n"
            "• Floating spots or dark strings (floaters) in vision\n"
            "• Blurred or fluctuating vision\n"
            "• Dark or empty areas in your field of vision\n"
            "• Impaired color vision\n"
            "• Vision loss in advanced stages\n"
            "*Note: In early stages (Mild to Moderate), DR often has NO noticeable symptoms! Annual screening is vital.*"
        )

    elif "prevent" in query or "avoid" in query or "lifestyle" in query:
        return (
            "**Key Prevention & Management Strategies:**\n"
            "• Keep **HbA1c below 6.5 - 7.0%** through medication, diet, and exercise.\n"
            "• Maintain blood pressure below **130/80 mmHg**.\n"
            "• Schedule an **annual dilated fundus examination** with an ophthalmologist.\n"
            "• Eat a low-glycemic, Mediterranean-style diet rich in leafy greens and omega-3s.\n"
            "• Avoid tobacco smoking completely."
        )

    elif "treatment" in query or "cure" in query or "laser" in query or "surgery" in query:
        return (
            "**Clinical Treatments for Diabetic Retinopathy:**\n"
            "1. **Anti-VEGF Injections:** Medications (e.g. Ranibizumab, Aflibercept) injected into the eye to reduce retinal swelling and suppress abnormal vessel growth.\n"
            "2. **Panretinal Photocoagulation (PRP Laser):** Laser treatment to shrink abnormal blood vessels in Proliferative DR.\n"
            "3. **Focal Grid Laser:** Reduces macular edema.\n"
            "4. **Vitrectomy:** Surgical removal of blood or scar tissue from the vitreous humor."
        )

    elif "meaning" in query or "result" in query or "prediction" in query or "score" in query:
        return (
            "**Understanding Your AI Prediction Result:**\n"
            "• **No DR (0):** Healthy retina. Repeat annual screening.\n"
            "• **Mild (1):** Microaneurysms detected. Optimize blood sugar control; follow up in 6 months.\n"
            "• **Moderate (2):** Exudates or hemorrhages visible. Strict diabetes control; follow up in 3-4 months.\n"
            "• **Severe (3):** Extensive hemorrhages. High risk of progression. Specialist evaluation in 1 month.\n"
            "• **Proliferative DR (4):** Emergency tier. Neovascularization present. Urgent retina specialist review mandated."
        )

    elif "follow" in query or "when to see doctor" in query:
        return (
            "**Follow-Up Guidelines:**\n"
            "• **No DR:** Every 12 months\n"
            "• **Mild DR:** Every 6 months\n"
            "• **Moderate DR:** Every 3–4 months\n"
            "• **Severe DR:** Within 1 month\n"
            "• **Proliferative DR:** Immediate (within 24–48 hours)"
        )

    else:
        return (
            "I am your VisionGuard AI Ophthalmic Assistant. You can ask me about:\n"
            "• What is Diabetic Retinopathy?\n"
            "• Causes and Risk Factors\n"
            "• Symptoms & Prevention\n"
            "• Available Treatments (Anti-VEGF, Laser, Vitrectomy)\n"
            "• How to interpret your AI scan results and follow-up schedules."
        )
