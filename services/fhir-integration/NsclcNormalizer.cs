using System.Globalization;
using System.Text.RegularExpressions;
using Hl7.Fhir.Model;

namespace OncologyCopilot.FhirIntegration;

public static partial class NsclcNormalizer
{
    private const string CaseIdentifierSystem = "https://oncology-copilot.dev/synthetic-case-id";
    private const string LoincSystem = "http://loinc.org";
    private static readonly string[] RequiredBiomarkers = ["EGFR", "ALK", "ROS1", "PD-L1 TPS"];

    public static CanonicalOncologyCase Normalize(Bundle bundle, string sourceBundleHash)
    {
        var entries = bundle.Entry.Where(entry => entry.Resource is not null).ToArray();
        var indexByResource = entries
            .Select((entry, index) => (Resource: entry.Resource!, Index: index))
            .ToDictionary(item => item.Resource, item => item.Index);
        var resources = entries.Select(entry => entry.Resource!).ToArray();
        var patient = resources.OfType<Patient>().Single();
        var condition = resources.OfType<Condition>().FirstOrDefault(IsNsclcCondition);
        var observations = resources.OfType<Observation>().ToArray();
        var reports = resources.OfType<DiagnosticReport>().ToArray();

        var caseId = patient.Identifier
            .First(item => item.System == CaseIdentifierSystem)
            .Value!;
        var referenceDate = DateOnly.FromDateTime(bundle.Timestamp!.Value.UtcDateTime);
        var birthDate = DateOnly.Parse(patient.BirthDate!, CultureInfo.InvariantCulture);

        var primarySite = BuildPrimarySite(condition, indexByResource);
        var histologyObservations = observations.Where(IsHistology).ToArray();
        var histology = BuildHistology(histologyObservations, indexByResource);
        var stageObservations = observations.Where(IsStage).ToArray();
        var stage = BuildStage(stageObservations, indexByResource);
        var biomarkerObservations = observations.Where(IsBiomarker).ToArray();
        var biomarkers = biomarkerObservations
            .Select(observation => BuildBiomarker(observation, indexByResource))
            .OrderBy(item => item.Name, StringComparer.Ordinal)
            .ToArray();
        var ecogObservations = observations.Where(IsEcog).ToArray();
        var performanceStatus = BuildPerformanceStatus(ecogObservations, indexByResource);
        var timeline = BuildTimeline(resources, indexByResource);
        var contradictions = BuildContradictions(
            histologyObservations,
            stageObservations,
            ecogObservations,
            indexByResource);
        var missingInformation = BuildMissingInformation(
            primarySite,
            histology,
            stage,
            biomarkers,
            performanceStatus,
            observations,
            reports);

        return new CanonicalOncologyCase(
            "1.0.0",
            caseId.ToLowerInvariant(),
            sourceBundleHash,
            new CanonicalPatient(
                true,
                patient.Id!,
                patient.Gender?.ToString().ToLowerInvariant() ?? "unknown",
                CalculateAge(birthDate, referenceDate),
                new PatientProvenance(
                    [Provenance(patient, indexByResource, "id")],
                    [Provenance(patient, indexByResource, "gender")],
                    [Provenance(patient, indexByResource, "birthDate")])),
            new CanonicalDisease(primarySite, histology, stage, biomarkers, performanceStatus),
            timeline,
            missingInformation,
            contradictions);
    }

    private static SourcedText BuildPrimarySite(
        Condition? condition,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var site = condition?.BodySite.FirstOrDefault();
        var coding = site?.Coding.FirstOrDefault();
        return new SourcedText(
            site?.Text ?? coding?.Display,
            coding?.Code,
            coding?.System,
            condition is null
                ? []
                : [Provenance(condition, indices, "bodySite[0]")]);
    }

    private static SourcedText BuildHistology(
        IReadOnlyList<Observation> observations,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var observation = observations.OrderByDescending(EffectiveDate).FirstOrDefault();
        var concept = observation?.Value as CodeableConcept;
        var coding = concept?.Coding.FirstOrDefault();
        return new SourcedText(
            concept?.Text ?? coding?.Display,
            coding?.Code,
            coding?.System,
            observation is null
                ? []
                : [Provenance(observation, indices, "valueCodeableConcept")]);
    }

    private static CanonicalStage BuildStage(
        IReadOnlyList<Observation> observations,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var observation = observations.OrderByDescending(EffectiveDate).FirstOrDefault();
        var raw = ConceptText(observation?.Value as CodeableConcept);
        var match = raw is null ? null : StagePattern().Match(raw);
        var t = match is { Success: true } ? match.Groups["t"].Value : null;
        var n = match is { Success: true } ? match.Groups["n"].Value : null;
        var m = match is { Success: true } ? match.Groups["m"].Value : null;
        var group = match is { Success: true } ? match.Groups["group"].Value : null;

        return new CanonicalStage(
            raw is null ? null : "AJCC 8th edition",
            EmptyToNull(group),
            EmptyToNull(t),
            EmptyToNull(n),
            EmptyToNull(m),
            observation is null
                ? []
                : [Provenance(observation, indices, "valueCodeableConcept")]);
    }

    private static CanonicalBiomarker BuildBiomarker(
        Observation observation,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var name = NormalizeBiomarkerName(observation.Code.Text ?? observation.Code.Coding.FirstOrDefault()?.Display ?? "Unknown");
        object? result = observation.Value switch
        {
            Quantity quantity => quantity.Value,
            CodeableConcept concept => ConceptText(concept),
            FhirString value => value.Value,
            _ => observation.Value?.ToString()
        };
        var unit = (observation.Value as Quantity)?.Unit;
        var interpretation = observation.Interpretation
            .SelectMany(item => item.Coding)
            .Select(item => item.Code)
            .FirstOrDefault();
        var status = interpretation switch
        {
            "POS" => "positive",
            "NEG" => "negative",
            "IND" => "indeterminate",
            _ when result?.ToString()?.Contains("not detected", StringComparison.OrdinalIgnoreCase) == true => "negative",
            _ when result is not null => "positive",
            _ => "unknown"
        };

        return new CanonicalBiomarker(
            name,
            result,
            unit,
            status,
            [Provenance(observation, indices, observation.Value is Quantity ? "valueQuantity" : "valueCodeableConcept")]);
    }

    private static PerformanceStatus BuildPerformanceStatus(
        IReadOnlyList<Observation> observations,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var observation = observations.OrderByDescending(EffectiveDate).FirstOrDefault();
        var score = observation?.Value switch
        {
            Integer integer => integer.Value,
            Quantity quantity => decimal.ToInt32(quantity.Value ?? 0),
            _ => null
        };
        return new PerformanceStatus(
            observation is null ? "unknown" : "ECOG",
            score,
            observation is null
                ? []
                : [Provenance(observation, indices, "valueInteger")]);
    }

    private static IReadOnlyList<TimelineEvent> BuildTimeline(
        IEnumerable<Resource> resources,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var events = new List<TimelineEvent>();
        foreach (var resource in resources)
        {
            switch (resource)
            {
                case Condition condition when DateOnlyFrom(condition.Onset) is { } date:
                    events.Add(new TimelineEvent(
                        date,
                        "diagnosis",
                        condition.Code?.Text ?? condition.Code?.Coding.FirstOrDefault()?.Display ?? "Diagnosis recorded",
                        [Provenance(condition, indices, "onsetDateTime")]));
                    break;
                case Observation observation when DateOnlyFrom(observation.Effective) is { } date:
                    events.Add(new TimelineEvent(
                        date,
                        IsHistology(observation) ? "pathology" : IsBiomarker(observation) ? "biomarker" : "other",
                        ObservationSummary(observation),
                        [Provenance(observation, indices, "effectiveDateTime")]));
                    break;
                case DiagnosticReport report when DateOnlyFrom(report.Effective) is { } date:
                    events.Add(new TimelineEvent(
                        date,
                        "imaging",
                        report.Conclusion ?? report.Code?.Text ?? "Diagnostic report",
                        [Provenance(report, indices, "conclusion")]));
                    break;
                case MedicationStatement statement when DateOnlyFrom(statement.Effective) is { } date:
                    events.Add(new TimelineEvent(
                        date,
                        "treatment",
                        MedicationText(statement.Medication),
                        [Provenance(statement, indices, "effectivePeriod")]));
                    break;
            }
        }

        return events.OrderBy(item => item.Date).ThenBy(item => item.Kind, StringComparer.Ordinal).ToArray();
    }

    private static IReadOnlyList<MissingInformation> BuildMissingInformation(
        SourcedText primarySite,
        SourcedText histology,
        CanonicalStage stage,
        IReadOnlyList<CanonicalBiomarker> biomarkers,
        PerformanceStatus performanceStatus,
        IReadOnlyList<Observation> observations,
        IReadOnlyList<DiagnosticReport> reports)
    {
        var missing = new List<MissingInformation>();
        AddMissing(primarySite.Value, "disease.primarySite", "critical", "Primary tumor site is required.", missing);
        AddMissing(histology.Value, "disease.histology", "critical", "Pathologic histology is required.", missing);
        AddMissing(stage.Group, "disease.stage.group", "critical", "Clinical stage group is required.", missing);
        if (performanceStatus.Score is null)
        {
            missing.Add(new MissingInformation(
                "disease.performanceStatus.score",
                "important",
                "A recent ECOG performance status is required for tumor-board review."));
        }

        foreach (var required in RequiredBiomarkers)
        {
            if (biomarkers.All(item => item.Name != required))
            {
                missing.Add(new MissingInformation(
                    $"disease.biomarkers.{required}",
                    "important",
                    $"{required} result is not present in the synthetic record."));
            }
        }

        if (stage.Group?.StartsWith("IV", StringComparison.OrdinalIgnoreCase) == true &&
            reports.All(report => !Contains(report.Code?.Text, "brain") && !Contains(report.Conclusion, "intracranial")))
        {
            missing.Add(new MissingInformation(
                "staging.brainImaging",
                "important",
                "No brain-staging report was found for metastatic NSCLC."));
        }

        if (observations.All(observation => !Contains(observation.Code.Text, "smoking")))
        {
            missing.Add(new MissingInformation(
                "history.smoking",
                "informational",
                "Smoking history is not documented."));
        }

        return missing;
    }

    private static IReadOnlyList<Contradiction> BuildContradictions(
        IReadOnlyList<Observation> histology,
        IReadOnlyList<Observation> stage,
        IReadOnlyList<Observation> ecog,
        IReadOnlyDictionary<Resource, int> indices)
    {
        var contradictions = new List<Contradiction>();
        AddContradiction(
            "disease.histology.value",
            histology,
            item => ConceptText(item.Value as CodeableConcept),
            "critical",
            indices,
            contradictions);
        AddContradiction(
            "disease.stage.group",
            stage,
            item => ConceptText(item.Value as CodeableConcept),
            "critical",
            indices,
            contradictions);
        AddContradiction(
            "disease.performanceStatus.score",
            ecog,
            item => (item.Value as Integer)?.Value?.ToString(CultureInfo.InvariantCulture),
            "important",
            indices,
            contradictions);
        return contradictions;
    }

    private static void AddContradiction(
        string field,
        IReadOnlyList<Observation> observations,
        Func<Observation, string?> selector,
        string severity,
        IReadOnlyDictionary<Resource, int> indices,
        ICollection<Contradiction> contradictions)
    {
        var values = observations
            .Select(selector)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value!)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (values.Length < 2)
        {
            return;
        }

        contradictions.Add(new Contradiction(
            field,
            values,
            severity,
            observations.Select(item => Provenance(item, indices, "value[x]")).ToArray()));
    }

    private static FieldProvenance Provenance(
        Resource resource,
        IReadOnlyDictionary<Resource, int> indices,
        string field) =>
        new(
            resource.TypeName,
            resource.Id!,
            $"$.entry[{indices[resource]}].resource.{field}");

    private static bool IsNsclcCondition(Condition condition) =>
        condition.Code?.Coding.Any(coding => coding.Code == "254637007") == true ||
        Contains(condition.Code?.Text, "non-small");

    private static bool IsHistology(Observation observation) =>
        HasCode(observation.Code, LoincSystem, "59847-4") || Contains(observation.Code.Text, "histology");

    private static bool IsStage(Observation observation) =>
        HasCode(observation.Code, LoincSystem, "21908-9") || Contains(observation.Code.Text, "stage");

    private static bool IsEcog(Observation observation) =>
        HasCode(observation.Code, LoincSystem, "89247-1") || Contains(observation.Code.Text, "ECOG");

    private static bool IsBiomarker(Observation observation)
    {
        var text = observation.Code.Text ?? observation.Code.Coding.FirstOrDefault()?.Display;
        return text is not null && new[] { "EGFR", "ALK", "ROS1", "PD-L1", "KRAS", "BRAF", "MET", "RET", "NTRK", "HER2", "ERBB2" }
            .Any(marker => text.Contains(marker, StringComparison.OrdinalIgnoreCase));
    }

    private static string NormalizeBiomarkerName(string name)
    {
        if (Contains(name, "PD-L1")) return "PD-L1 TPS";
        if (Contains(name, "HER2") || Contains(name, "ERBB2")) return "HER2";
        return new[] { "EGFR", "ALK", "ROS1", "KRAS", "BRAF", "MET", "RET", "NTRK" }
            .FirstOrDefault(marker => name.Contains(marker, StringComparison.OrdinalIgnoreCase)) ?? name;
    }

    private static string ObservationSummary(Observation observation)
    {
        var label = observation.Code.Text ?? observation.Code.Coding.FirstOrDefault()?.Display ?? "Observation";
        var value = observation.Value switch
        {
            CodeableConcept concept => ConceptText(concept),
            Quantity quantity => $"{quantity.Value} {quantity.Unit}".Trim(),
            Integer integer => integer.Value?.ToString(CultureInfo.InvariantCulture),
            FhirString text => text.Value,
            _ => observation.Value?.ToString()
        };
        return string.IsNullOrWhiteSpace(value) ? label : $"{label}: {value}";
    }

    private static string? ConceptText(CodeableConcept? concept) =>
        concept?.Text ?? concept?.Coding.FirstOrDefault()?.Display ?? concept?.Coding.FirstOrDefault()?.Code;

    private static DateTimeOffset EffectiveDate(Observation observation) =>
        DateTimeOffsetFrom(observation.Effective) ?? DateTimeOffset.MinValue;

    private static DateOnly? DateOnlyFrom(DataType? value) =>
        DateTimeOffsetFrom(value) is { } date ? DateOnly.FromDateTime(date.UtcDateTime) : null;

    private static string MedicationText(DataType? medication) => medication switch
    {
        CodeableConcept concept => ConceptText(concept) ?? "Medication recorded",
        ResourceReference reference => reference.Display ?? reference.Reference ?? "Medication recorded",
        _ => medication?.ToString() ?? "Medication recorded"
    };

    private static DateTimeOffset? DateTimeOffsetFrom(DataType? value) => value switch
    {
        FhirDateTime date => date.ToDateTimeOffset(TimeSpan.Zero),
        Period period when period.StartElement is not null => period.StartElement.ToDateTimeOffset(TimeSpan.Zero),
        _ => null
    };

    private static bool HasCode(CodeableConcept? concept, string system, string code) =>
        concept?.Coding.Any(item => item.System == system && item.Code == code) == true;

    private static bool Contains(string? value, string term) =>
        value?.Contains(term, StringComparison.OrdinalIgnoreCase) == true;

    private static void AddMissing(
        string? value,
        string field,
        string severity,
        string reason,
        ICollection<MissingInformation> missing)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            missing.Add(new MissingInformation(field, severity, reason));
        }
    }

    private static int CalculateAge(DateOnly birthDate, DateOnly referenceDate)
    {
        var age = referenceDate.Year - birthDate.Year;
        if (birthDate > referenceDate.AddYears(-age)) age--;
        return age;
    }

    private static string? EmptyToNull(string? value) => string.IsNullOrWhiteSpace(value) ? null : value;

    [GeneratedRegex(
        @"(?<t>c?T[0-4][a-c]?)\s+(?<n>c?N[0-3])\s+(?<m>c?M[0-1][a-c]?).*?stage\s+(?<group>(?:IV|III|II|I)[A-C]?[0-3]?)(?:\b|$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex StagePattern();
}
