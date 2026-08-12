using System.Text.Json;
using OncologyCopilot.FhirIntegration;
using Xunit;

namespace OncologyCopilot.FhirIntegration.Tests;

public sealed class Week6SuiteTests
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private readonly FhirBundleProcessor _processor = new();

    public static IEnumerable<object[]> CaseIds => Enumerable.Range(1, 60)
        .Select(number => new object[] { $"nsclc-{number:000}" });

    [Theory]
    [MemberData(nameof(CaseIds))]
    public void GeneratedCaseMatchesEngineeringGold(string caseId)
    {
        using var bundle = JsonDocument.Parse(File.ReadAllText(FixturePath(caseId)));
        using var gold = JsonDocument.Parse(File.ReadAllText(GoldPath(caseId)));

        var result = _processor.Process(bundle.RootElement);
        var goldRoot = gold.RootElement;
        var expectedValidation = goldRoot.GetProperty("expectedValidation");
        var expectedValid = expectedValidation.GetProperty("valid").GetBoolean();

        Assert.Equal(expectedValid, result.Validation.IsValid);
        foreach (var code in expectedValidation.GetProperty("issueCodes").EnumerateArray())
        {
            Assert.Contains(result.Validation.Issues, issue => issue.Code == code.GetString());
        }

        if (!expectedValid)
        {
            Assert.Null(result.CanonicalCase);
            return;
        }

        var canonical = Assert.IsType<CanonicalOncologyCase>(result.CanonicalCase);
        var actual = JsonSerializer.SerializeToElement(canonical, JsonOptions);
        Assert.Equal(caseId, canonical.CaseId);
        AssertExpectedFields(goldRoot.GetProperty("expectedFields"), actual);
        AssertExpectedBiomarkers(goldRoot.GetProperty("expectedBiomarkers"), actual);
        AssertExpectedProvenance(goldRoot.GetProperty("expectedProvenance"), actual);
        AssertExpectedFieldList(
            goldRoot.GetProperty("expectedMissingInformation"),
            actual.GetProperty("missingInformation"));
        AssertExpectedFieldList(
            goldRoot.GetProperty("expectedContradictions"),
            actual.GetProperty("contradictions"));
    }

    private static void AssertExpectedFields(JsonElement expectedFields, JsonElement actual)
    {
        foreach (var expected in expectedFields.EnumerateObject())
        {
            var actualValue = GetByPath(actual, expected.Name);
            AssertJsonValue(expected.Value, actualValue, expected.Name);
        }
    }

    private static void AssertExpectedBiomarkers(JsonElement expectedBiomarkers, JsonElement actual)
    {
        var actualBiomarkers = GetByPath(actual, "disease.biomarkers").EnumerateArray().ToArray();
        foreach (var expected in expectedBiomarkers.EnumerateArray())
        {
            var name = expected.GetProperty("name").GetString();
            var actualBiomarker = actualBiomarkers.Single(item =>
                string.Equals(item.GetProperty("name").GetString(), name, StringComparison.OrdinalIgnoreCase));
            foreach (var property in new[] { "result", "unit", "status" })
            {
                AssertJsonValue(
                    expected.GetProperty(property),
                    actualBiomarker.GetProperty(property),
                    $"disease.biomarkers.{name}.{property}");
            }
        }
    }

    private static void AssertExpectedProvenance(JsonElement expectedProvenance, JsonElement actual)
    {
        foreach (var expected in expectedProvenance.EnumerateObject())
        {
            var actualSources = GetActualProvenance(actual, expected.Name).EnumerateArray().ToArray();
            var expectedSources = expected.Value.EnumerateArray().ToArray();
            Assert.Equal(expectedSources.Length, actualSources.Length);
            for (var index = 0; index < expectedSources.Length; index++)
            {
                foreach (var property in new[] { "resourceType", "resourceId", "jsonPath" })
                {
                    Assert.Equal(
                        expectedSources[index].GetProperty(property).GetString(),
                        actualSources[index].GetProperty(property).GetString());
                }
            }
        }
    }

    private static JsonElement GetActualProvenance(JsonElement actual, string field)
    {
        if (field == "patient.sex") return GetByPath(actual, "patient.provenance.sex");
        if (field == "patient.ageYears") return GetByPath(actual, "patient.provenance.ageYears");
        if (field.StartsWith("disease.primarySite.", StringComparison.Ordinal))
            return GetByPath(actual, "disease.primarySite.provenance");
        if (field.StartsWith("disease.histology.", StringComparison.Ordinal))
            return GetByPath(actual, "disease.histology.provenance");
        if (field.StartsWith("disease.stage.", StringComparison.Ordinal))
            return GetByPath(actual, "disease.stage.provenance");
        if (field.StartsWith("disease.performanceStatus.", StringComparison.Ordinal))
            return GetByPath(actual, "disease.performanceStatus.provenance");

        const string biomarkerPrefix = "disease.biomarkers.";
        if (field.StartsWith(biomarkerPrefix, StringComparison.Ordinal))
        {
            var name = field[biomarkerPrefix.Length..];
            var biomarker = GetByPath(actual, "disease.biomarkers")
                .EnumerateArray()
                .Single(item => string.Equals(
                    item.GetProperty("name").GetString(),
                    name,
                    StringComparison.OrdinalIgnoreCase));
            return biomarker.GetProperty("provenance");
        }

        throw new InvalidOperationException($"No provenance route is defined for '{field}'.");
    }

    private static void AssertExpectedFieldList(JsonElement expected, JsonElement actual)
    {
        var expectedFields = expected.EnumerateArray().Select(item => item.GetString()).ToArray();
        var actualFields = actual.EnumerateArray()
            .Select(item => item.GetProperty("field").GetString())
            .ToArray();
        Assert.Equal(expectedFields, actualFields);
    }

    private static JsonElement GetByPath(JsonElement root, string path)
    {
        var current = root;
        foreach (var segment in path.Split('.'))
        {
            current = current.GetProperty(segment);
        }

        return current;
    }

    private static void AssertJsonValue(JsonElement expected, JsonElement actual, string field)
    {
        Assert.True(
            JsonValuesEqual(expected, actual),
            $"Field '{field}' expected {expected.GetRawText()} but found {actual.GetRawText()}.");
    }

    private static bool JsonValuesEqual(JsonElement expected, JsonElement actual) =>
        expected.ValueKind == actual.ValueKind && (expected.ValueKind switch
        {
            JsonValueKind.String => string.Equals(
                expected.GetString(),
                actual.GetString(),
                StringComparison.OrdinalIgnoreCase),
            JsonValueKind.Number => expected.GetDecimal() == actual.GetDecimal(),
            JsonValueKind.Null => true,
            JsonValueKind.True or JsonValueKind.False => expected.GetBoolean() == actual.GetBoolean(),
            _ => expected.GetRawText() == actual.GetRawText()
        });

    private static string FixturePath(string caseId) =>
        Path.Combine(AppContext.BaseDirectory, "Fixtures", $"{caseId}.bundle.json");

    private static string GoldPath(string caseId) =>
        Path.Combine(AppContext.BaseDirectory, "Gold", caseId, "gold.json");
}
