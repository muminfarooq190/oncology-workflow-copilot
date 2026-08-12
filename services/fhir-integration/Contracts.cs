namespace OncologyCopilot.FhirIntegration;

public sealed record ValidationIssue(
    string Severity,
    string Code,
    string Message,
    string? JsonPath = null,
    string? ResourceReference = null);

public sealed record FhirValidationResult(
    bool IsValid,
    string FhirRelease,
    string ValidationLevel,
    IReadOnlyDictionary<string, int> ResourceCounts,
    IReadOnlyList<ValidationIssue> Issues);

public sealed record FhirProcessingResult(
    FhirValidationResult Validation,
    CanonicalOncologyCase? CanonicalCase);

public sealed record CanonicalOncologyCase(
    string SchemaVersion,
    string CaseId,
    string SourceBundleHash,
    CanonicalPatient Patient,
    CanonicalDisease Disease,
    IReadOnlyList<TimelineEvent> ClinicalTimeline,
    IReadOnlyList<MissingInformation> MissingInformation,
    IReadOnlyList<Contradiction> Contradictions);

public sealed record CanonicalPatient(
    bool Synthetic,
    string SourcePatientId,
    string Sex,
    int AgeYears,
    PatientProvenance Provenance);

public sealed record PatientProvenance(
    IReadOnlyList<FieldProvenance> SourcePatientId,
    IReadOnlyList<FieldProvenance> Sex,
    IReadOnlyList<FieldProvenance> AgeYears);

public sealed record CanonicalDisease(
    SourcedText PrimarySite,
    SourcedText Histology,
    CanonicalStage Stage,
    IReadOnlyList<CanonicalBiomarker> Biomarkers,
    PerformanceStatus PerformanceStatus);

public sealed record SourcedText(
    string? Value,
    string? Code,
    string? System,
    IReadOnlyList<FieldProvenance> Provenance);

public sealed record CanonicalStage(
    string? System,
    string? Group,
    string? ClinicalT,
    string? ClinicalN,
    string? ClinicalM,
    IReadOnlyList<FieldProvenance> Provenance);

public sealed record CanonicalBiomarker(
    string Name,
    object? Result,
    string? Unit,
    string Status,
    IReadOnlyList<FieldProvenance> Provenance);

public sealed record PerformanceStatus(
    string Scale,
    int? Score,
    IReadOnlyList<FieldProvenance> Provenance);

public sealed record TimelineEvent(
    DateOnly Date,
    string Kind,
    string Summary,
    IReadOnlyList<FieldProvenance> Provenance);

public sealed record MissingInformation(
    string Field,
    string Severity,
    string Reason);

public sealed record Contradiction(
    string Field,
    IReadOnlyList<string> Values,
    string Severity,
    IReadOnlyList<FieldProvenance> Provenance);

public sealed record FieldProvenance(
    string ResourceType,
    string ResourceId,
    string JsonPath);
