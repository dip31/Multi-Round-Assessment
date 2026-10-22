// Keeps the UI from issuing POST /blueprint/generate requests the backend
// always refuses. A role-assessment (llm_role_assessment) blueprint is never
// overwritten: the backend answers 409 whenever a blueprint already exists for
// an LLM role-assessment pattern, with or without force. Evidence-based
// blueprints keep the existing explicit-recalculation versioning flow.

export function isRoleAssessmentProvenance(provenance) {
    if (!provenance || typeof provenance !== 'object') return false;
    return provenance.generation_method === 'llm_role_assessment'
        || provenance.classification === 'llm_role_assessment';
}

export function resolveBlueprintGenerationRequest({ hasBlueprint = false, force = false, provenance = null } = {}) {
    if (hasBlueprint && isRoleAssessmentProvenance(provenance)) {
        return {
            allowed: false,
            reason: 'role_assessment_blueprint_immutable',
            message: 'This role-specific blueprint is locked to its approved role assessment and cannot be recalculated. The existing approved version is kept.',
        };
    }
    return { allowed: true, force: Boolean(force) };
}
