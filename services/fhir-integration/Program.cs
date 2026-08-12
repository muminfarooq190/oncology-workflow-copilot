using System.Text.Json;
using OncologyCopilot.FhirIntegration;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.AddSingleton<FhirBundleProcessor>();

var app = builder.Build();
app.UseExceptionHandler();

app.MapGet("/health", () => Results.Ok(new
{
    status = "ok",
    service = "fhir-integration",
    version = "0.2.0",
    fhirRelease = "R4"
}));

app.MapPost("/v1/fhir/validate", (JsonElement bundle, FhirBundleProcessor processor) =>
{
    var result = processor.Validate(bundle);
    return result.IsValid
        ? Results.Ok(result)
        : Results.Json(result, statusCode: StatusCodes.Status422UnprocessableEntity);
});

app.MapPost("/v1/fhir/normalize", (JsonElement bundle, FhirBundleProcessor processor) =>
{
    var result = processor.Process(bundle);
    return result.Validation.IsValid
        ? Results.Ok(result)
        : Results.Json(result, statusCode: StatusCodes.Status422UnprocessableEntity);
});

app.Run();

public partial class Program { }
