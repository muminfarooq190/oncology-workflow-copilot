using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();

var app = builder.Build();
app.UseExceptionHandler();

app.MapGet("/health", () => Results.Ok(new
{
    status = "ok",
    service = "fhir-integration",
    version = "0.1.0"
}));

app.MapPost("/v1/fhir/validate", (JsonElement payload) =>
{
    if (!payload.TryGetProperty("resourceType", out var resourceType) ||
        resourceType.GetString() != "Bundle")
    {
        return Results.ValidationProblem(new Dictionary<string, string[]>
        {
            ["resourceType"] = ["FHIR input must have resourceType Bundle."]
        });
    }

    if (!IsExplicitlySynthetic(payload))
    {
        return Results.ValidationProblem(new Dictionary<string, string[]>
        {
            ["meta.tag"] = ["Only bundles explicitly tagged as synthetic are accepted."]
        });
    }

    var resourceCounts = CountResourceTypes(payload);
    return Results.Ok(new
    {
        valid = true,
        profile = "FHIR R4 foundation envelope",
        canonicalContractVersion = "1.0.0",
        resourceCounts,
        limitations = new[]
        {
            "FHIR profile validation and canonical mapping are implemented in Week 6."
        }
    });
});

app.Run();

static bool IsExplicitlySynthetic(JsonElement bundle)
{
    if (!bundle.TryGetProperty("meta", out var meta) ||
        !meta.TryGetProperty("tag", out var tags) ||
        tags.ValueKind != JsonValueKind.Array)
    {
        return false;
    }

    return tags.EnumerateArray().Any(tag =>
        tag.TryGetProperty("system", out var system) &&
        system.GetString() == "https://oncology-copilot.dev/tags" &&
        tag.TryGetProperty("code", out var code) &&
        code.GetString() == "synthetic");
}

static Dictionary<string, int> CountResourceTypes(JsonElement bundle)
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
        if (string.IsNullOrWhiteSpace(name))
        {
            continue;
        }

        counts[name] = counts.GetValueOrDefault(name) + 1;
    }

    return counts;
}

public partial class Program;

