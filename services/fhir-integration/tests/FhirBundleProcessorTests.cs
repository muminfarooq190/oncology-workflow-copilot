using System.Text.Json;
using System.Text.Json.Nodes;
using OncologyCopilot.FhirIntegration;
using Xunit;

namespace OncologyCopilot.FhirIntegration.Tests;

public sealed class FhirBundleProcessorTests
{
    private readonly FhirBundleProcessor _processor = new();

    [Fact]
    public void CompleteNsclcBundleNormalizesCriticalFieldsWithProvenance()
    {
        using var document = LoadFixture();

        var result = _processor.Process(document.RootElement);

        Assert.True(result.Validation.IsValid);
        var canonical = Assert.IsType<CanonicalOncologyCase>(result.CanonicalCase);
        Assert.Equal("nsclc-001", canonical.CaseId);
        Assert.Equal(68, canonical.Patient.AgeYears);
        Assert.Equal("Poorly differentiated lung adenocarcinoma", canonical.Disease.Histology.Value);
        Assert.Equal("IVB", canonical.Disease.Stage.Group);
        Assert.Equal("cT2a", canonical.Disease.Stage.ClinicalT);
        Assert.Equal("cN2", canonical.Disease.Stage.ClinicalN);
        Assert.Equal("cM1c", canonical.Disease.Stage.ClinicalM);
        Assert.Equal(1, canonical.Disease.PerformanceStatus.Score);
        Assert.Empty(canonical.MissingInformation);
        Assert.Empty(canonical.Contradictions);
        Assert.All(
            canonical.Disease.Histology.Provenance,
            source => Assert.StartsWith("$.entry[", source.JsonPath));
        Assert.EndsWith(".resource.gender", Assert.Single(canonical.Patient.Provenance.Sex).JsonPath);
    }

    [Fact]
    public void BundleWithoutSyntheticMarkerIsRejected()
    {
        var node = LoadFixtureNode();
        node["meta"]!["tag"] = new JsonArray();
        using var document = JsonDocument.Parse(node.ToJsonString());

        var result = _processor.Process(document.RootElement);

        Assert.False(result.Validation.IsValid);
        Assert.Null(result.CanonicalCase);
        Assert.Contains(result.Validation.Issues, issue => issue.Code == "synthetic-marker-required");
    }

    [Fact]
    public void UnresolvedPatientReferenceIsRejected()
    {
        var node = LoadFixtureNode();
        var entries = node["entry"]!.AsArray();
        var observation = entries
            .Select(item => item!["resource"])
            .First(resource => resource!["resourceType"]!.GetValue<string>() == "Observation");
        observation!["subject"]!["reference"] = "Patient/missing";
        using var document = JsonDocument.Parse(node.ToJsonString());

        var result = _processor.Validate(document.RootElement);

        Assert.False(result.IsValid);
        Assert.Contains(result.Issues, issue => issue.Code == "unresolved-reference");
    }

    [Fact]
    public void MissingEcogProducesImportantMissingInformation()
    {
        var node = LoadFixtureNode();
        var entries = node["entry"]!.AsArray();
        var ecog = entries.First(entry =>
            entry!["resource"]?["id"]?.GetValue<string>() == "observation-ecog-001");
        entries.Remove(ecog);
        using var document = JsonDocument.Parse(node.ToJsonString());

        var result = _processor.Process(document.RootElement);

        Assert.True(result.Validation.IsValid);
        Assert.Contains(
            result.CanonicalCase!.MissingInformation,
            item => item.Field == "disease.performanceStatus.score" && item.Severity == "important");
    }

    [Fact]
    public void ConflictingStageObservationsAreSurfaced()
    {
        var node = LoadFixtureNode();
        var entries = node["entry"]!.AsArray();
        var stageEntry = entries.First(entry =>
            entry!["resource"]?["id"]?.GetValue<string>() == "observation-stage-001")!;
        var conflicting = stageEntry.DeepClone();
        conflicting["fullUrl"] = "urn:uuid:observation-stage-conflict";
        conflicting["resource"]!["id"] = "observation-stage-conflict";
        conflicting["resource"]!["effectiveDateTime"] = "2026-04-03";
        conflicting["resource"]!["valueCodeableConcept"]!["text"] = "cT2a cN2 cM0, stage IIIA";
        entries.Add(conflicting);
        using var document = JsonDocument.Parse(node.ToJsonString());

        var result = _processor.Process(document.RootElement);

        Assert.True(result.Validation.IsValid);
        Assert.Contains(
            result.CanonicalCase!.Contradictions,
            item => item.Field == "disease.stage.group" && item.Severity == "critical");
        Assert.Equal("IIIA", result.CanonicalCase.Disease.Stage.Group);
    }

    private static JsonDocument LoadFixture() =>
        JsonDocument.Parse(File.ReadAllText(FixturePath()));

    private static JsonObject LoadFixtureNode() =>
        JsonNode.Parse(File.ReadAllText(FixturePath()))!.AsObject();

    private static string FixturePath() =>
        Path.Combine(AppContext.BaseDirectory, "Fixtures", "nsclc-001.bundle.json");
}
