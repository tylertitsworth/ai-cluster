# mealie

![Version: 0.0.20](https://img.shields.io/badge/Version-0.0.20-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: v2.8.0](https://img.shields.io/badge/AppVersion-v2.8.0-informational?style=flat-square)

A Helm chart for deploying Mealie to a Kubernetes cluster with built in postgres support. The original chart can be found at https://artifacthub.io/packages/helm/smarthall/mealie.

## Maintainers

| Name | Email | Url |
| ---- | ------ | --- |
| SkyHook | <eleventhour58@gmail.com> |  |

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` |  |
| autoscaling.enabled | bool | `false` |  |
| autoscaling.maxReplicas | int | `100` |  |
| autoscaling.minReplicas | int | `1` |  |
| autoscaling.targetCPUUtilizationPercentage | int | `80` |  |
| fullnameOverride | string | `""` |  |
| image.pgtag | string | `"15"` | Which version of postgres to use if enabled |
| image.postgresRepo | string | `"postgres"` |  |
| image.pullPolicy | string | `"Always"` | The pull policy for mealie images |
| image.repository | string | `"ghcr.io/mealie-recipes/mealie"` | The repository for docker images to use |
| image.tag | string | `""` | Override the default app version with another version |
| imagePullSecrets | list | `[]` |  |
| ingress.annotations | object | `{}` |  |
| ingress.className | string | `""` |  |
| ingress.enabled | bool | `false` |  |
| ingress.hosts[0].host | string | `"chart-example.local"` |  |
| ingress.hosts[0].paths[0].path | string | `"/"` |  |
| ingress.hosts[0].paths[0].pathType | string | `"ImplementationSpecific"` |  |
| ingress.tls | list | `[]` |  |
| mealie.env[0] | object | `{"name":"ALLOW_SIGNUP","value":false}` | Basic environment variables for mealie, more can be found at https://docs.mealie.io/documentation/getting-started/installation/backend-config/. |
| mealie.env[10].name | string | `"POSTGRES_DB"` |  |
| mealie.env[10].value | string | `"mealie"` |  |
| mealie.env[11] | object | `{"name":"OPENAI_BASE_URL","value":"INSERT_YOUR_OPENAI_BASE_URL_HERE"}` | OpenAI API configuration |
| mealie.env[12].name | string | `"OPENAI_API_KEY"` |  |
| mealie.env[12].value | string | `"INSERT_YOUR_OPENAI_API_KEY_HERE"` |  |
| mealie.env[13].name | string | `"OPENAI_MODEL"` |  |
| mealie.env[13].value | string | `"gpt-4.1"` |  |
| mealie.env[1].name | string | `"DEFAULT_GROUP"` |  |
| mealie.env[1].value | string | `"HOME"` |  |
| mealie.env[2].name | string | `"DEFAULT_HOUSEHOLD"` |  |
| mealie.env[2].value | string | `"FAMILY"` |  |
| mealie.env[3].name | string | `"SECURITY_MAX_LOGIN_ATTEMPTS"` |  |
| mealie.env[3].value | int | `5` |  |
| mealie.env[4].name | string | `"SECURITY_USER_LOCKOUT_TIME"` |  |
| mealie.env[4].value | int | `24` |  |
| mealie.env[5] | object | `{"name":"DB_ENGINE","value":"sqlite"}` | Postgres Variables, to use postgres, change DB_ENGINE to postgres. The other variables are set to use the included postgres database by default. |
| mealie.env[6].name | string | `"POSTGRES_USER"` |  |
| mealie.env[6].value | string | `"mealie"` |  |
| mealie.env[7].name | string | `"POSTGRES_PASSWORD"` |  |
| mealie.env[7].value | string | `"mealie"` |  |
| mealie.env[8].name | string | `"POSTGRES_SERVER"` |  |
| mealie.env[8].value | string | `"postgres-mealie"` |  |
| mealie.env[9].name | string | `"POSTGRES_PORT"` |  |
| mealie.env[9].value | string | `"5432"` |  |
| mealie.initialDelaySeconds | int | `10` | The initial delay for the liveness and readiness probes for mealie |
| mealie.replicas | int | `1` | The number of api replicas to run. Only set above 1 if using postgres |
| mealie.service.port | int | `9000` |  |
| mealie.service.type | string | `"ClusterIP"` |  |
| nameOverride | string | `""` |  |
| nodeSelector | object | `{}` |  |
| podAnnotations | object | `{}` |  |
| podSecurityContext | object | `{}` |  |
| postgres | object | `{"enabled":false,"env":[{"name":"PGDATA","value":"/var/lib/postgresql/data/pgdata"},{"name":"POSTGRES_USER","value":"mealie"},{"name":"POSTGRES_PASSWORD","value":"mealie"},{"name":"POSTGRES_DB","value":"mealie"},{"name":"PG_USER","value":"mealie"}],"initialDelaySeconds":10,"service":{"port":5432,"type":"ClusterIP"}}` | Set postgres to true if you want to use the included postgres database. |
| postgres.env | list | `[{"name":"PGDATA","value":"/var/lib/postgresql/data/pgdata"},{"name":"POSTGRES_USER","value":"mealie"},{"name":"POSTGRES_PASSWORD","value":"mealie"},{"name":"POSTGRES_DB","value":"mealie"},{"name":"PG_USER","value":"mealie"}]` | # Postgres environment variables, leave PGDATA unchanged unless you know what you are doing. |
| resources | object | `{}` |  |
| securityContext | object | `{}` |  |
| serviceAccount.annotations | object | `{}` |  |
| serviceAccount.create | bool | `true` |  |
| serviceAccount.name | string | `""` |  |
| storage.accessModeMealie | string | `"ReadWriteMany"` | The accessMode that is supported. |
| storage.accessModePostgres | string | `"ReadWriteMany"` |  |
| storage.className | string | `""` | The storage class to use |
| storage.enabled | bool | `true` | Enable storage that isn't emphemeral |
| storage.mealieSize | string | `"4G"` | The size of the storage to allocate |
| storage.postgresSize | string | `"8G"` |  |
| tolerations | list | `[]` |  |

----------------------------------------------
Autogenerated from chart metadata using [helm-docs v1.14.2](https://github.com/norwoodj/helm-docs/releases/v1.14.2)
