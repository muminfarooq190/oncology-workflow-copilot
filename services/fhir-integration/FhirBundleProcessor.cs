using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Hl7.Fhir.Model;
using Hl7.Fhir.Serialization;

namespace OncologyCopilot.FhirIntegration;

public sealed class FhirBundleProcessor
{
    private const string SyntheticTagSystem = "https://oncology-copilot.dev/tags";
    private const string CaseIdentifierSystem = "https://oncology-copilot.dev/synthetic-case-id";
    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);

    public FhirValidationResult Validate(JsonElement bundleElement)
    {
        var issues = new List<ValidationIssue>();
        var resourceCounts = CountResourceTypes(bundleElement);

        if (!HasResourceType(bundleElement, "Bundle"))
        {
            issues.Add(Error("invalid-resource-type", "FHIR input must have resourceType Bundle.", "$.resourceType"));
            return Result(issues, resourceCounts);
        }

        if (!IsExplicitlySynthetic(bundleElement))
        {
            issues.Add(Error(
                "synthetic-marker-required",
                "Only bundles explicitly tagged as synthetic are accepted.",
                "$.meta.tag"));
        }

        Bundle? bundle = null;
        try
        {
            bundle = FhirJsonDeserializer.STRICT.DeserializeResource(bundleElement.GetRawText()) as Bundle;
            if (bundle is null)
            {
                issues.Add(Error("invalid-resource-type", "FHIR input must deserialize to a Bundle."));
            }
        }
        catch (DeserializationFailedException exception)
        {
            foreach (var issue in exception.Exceptions)
            {
                issues.Add(Error(
                    "fhir-deserialization-error",
                    $"[{issue.ErrorCode}] {issue.Message}"));
            }
        }

        if (bundle is not null)
        {
            ValidateBundleRules(bundle, issues);
        }

        return Result(issues, resourceCounts);
    }

    public FhirProcessingResult Process(JsonElement bundleElement)
    {
        var validation = Validate(bundleElement);
        if (!validation.IsValid)
        {
            return new FhirProcessingResult(validation, null);
        }

        var bundle = (Bundle)FhirJsonDeserializer.STRICT.DeserializeResource(bundleElement.GetRawText());
        var canonicalCase = NsclcNormalizer.Normalize(bundle, ComputeHash(bundleElement));
        return new FhirProcessingResult(validation, canonicalCase);
    }

    private static void ValidateBundleRules(Bundle bundle, ICollection<ValidationIssue> issues)
    {
        var resources = bundle.Entry
            .Where(entry => entry.Resource is not null)
            .Select(entry => entry.Resource!)
            .ToArray();
        var patients = resources.OfType<Patient>().ToArray();

        if (patients.Length != 1)
        {
            issues.Add(Error(
                "single-patient-required",
                $"Exactly one Patient is required; found {patients.Length}.",
                "$.entry"));
        }

        var resolvableReferences = new HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in bundle.Entry.Where(entry => entry.Resource is not null))
        {
            if (!string.IsNullOrWhiteSpace(entry.FullUrl))
            {
                resolvableReferences.Add(entry.FullUrl);
            }

            if (!string.IsNullOrWhiteSpace(entry.Resource!.Id))
            {
                resolvableReferences.Add($"{entry.Resource.TypeName}/{entry.Resource.Id}");
            }
        }

        foreach (var (resource, reference, path) in SubjectReferences(resources))
        {
            if (string.IsNullOrWhiteSpace(reference) || resolvableReferences.Contains(reference))
            {
                continue;
            }

            issues.Add(Error(
                "unresolved-reference",
                $"Subject reference '{reference}' cannot be resolved inside the Bundle.",
                path,
                $"{resource.TypeName}/{resource.Id}"));
        }

        if (patients.Length == 1 && !patients[0].Identifier.Any(item =>
                item.System == CaseIdentifierSystem && !string.IsNullOrWhiteSpace(item.Value)))
        {
            issues.Add(Error(
                "case-identifier-required",
                $"Patient.identifier with system '{CaseIdentifierSystem}' is required.",
                "$.entry[?(@.resource.resourceType == 'Patient')].resource.identifier"));
        }

        if (bundle.Timestamp is null)
        {
            issues.Add(Error(
                "bundle-timestamp-required",
                "Bundle.timestamp is required so age and timeline calculations remain deterministic.",
                "$.timestamp"));
        }

        if (patients.Length == 1 && string.IsNullOrWhiteSpace(patients[0].BirthDate))
        {
            issues.Add(Error(
                "birth-date-required",
                "Patient.birthDate is required for the canonical case contract.",
                "$.entry[?(@.resource.resourceType == 'Patient')].resource.birthDate"));
        }
    }

    private static IEnumerable<(Resource Resource, string? Reference, string Path)> SubjectReferences(
        IEnumerable<Resource> resources)
    {
        foreach (var resource in resources)
        {
            switch (resource)
            {
                case Condition condition:
                    yield return (condition, condition.Subject?.Reference, "$.entry[*].resource.subject.reference");
                    break;
                case Observation observation:
                    yield return (observation, observation.Subject?.Reference, "$.entry[*].resource.subject.reference");
                    break;
                case DiagnosticReport report:
                    yield return (report, report.Subject?.Reference, "$.entry[*].resource.subject.reference");
                    break;
                case Procedure procedure:
                    yield return (procedure, procedure.Subject?.Reference, "$.entry[*].resource.subject.reference");
                    break;
                case MedicationStatement statement:
                    yield return (statement, statement.Subject?.Reference, "$.entry[*].resource.subject.reference");
                    break;
            }
        }
    }

    private static IReadOnlyDictionary<string, int> CountResourceTypes(JsonElement bundle)
    {
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        if (!bundle.TryGetProperty("entry", out var entries) || entries.ValueKind != JsonValueKind.Array)
        {
            return counts;
        }

        foreach (var entry in entries.EnumerateArray())
        {
            if (!entry.TryGetProperty("resource", out var resource) ||
                !resource.TryGetProperty("resourceType", out var resourceType))
            {
                continue;
            }

            var name = resourceType.GetString();
            if (!string.IsNullOrWhiteSpace(name))
            {
                counts[name] = counts.GetValueOrDefault(name) + 1;
            }
        }

        return counts;
    }

    private static bool HasResourceType(JsonElement resource, string expected) =>
        resource.TryGetProperty("resourceType", out var resourceType) &&
        resourceType.GetString() == expected;

    private static bool IsExplicitlySynthetic(JsonElement bundle)
    {
        if (!bundle.TryGetProperty("meta", out var meta) ||
            !meta.TryGetProperty("tag", out var tags) ||
            tags.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        return tags.EnumerateArray().Any(tag =>
            tag.TryGetProperty("system", out var system) &&
            system.GetString() == SyntheticTagSystem &&
            tag.TryGetProperty("code", out var code) &&
            code.GetString() == "synthetic");
    }

    private static string ComputeHash(JsonElement bundle)
    {
        var canonicalJson = JsonSerializer.Serialize(bundle, SerializerOptions);
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(canonicalJson));
        return $"sha256:{Convert.ToHexString(bytes).ToLowerInvariant()}";
    }

    private static FhirValidationResult Result(
        IReadOnlyList<ValidationIssue> issues,
        IReadOnlyDictionary<string, int> counts) =>
        new(
            !issues.Any(issue => issue.Severity == "error"),
            "R4",
            "Firely R4 parser/model validation plus bundle reference and synthetic-data rules",
            counts,
            issues);

    private static ValidationIssue Error(
        string code,
        string message,
        string? jsonPath = null,
        string? resourceReference = null) =>
        new("error", code, message, jsonPath, resourceReference);
}
