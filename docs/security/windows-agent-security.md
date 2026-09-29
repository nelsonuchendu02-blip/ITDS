\# ITDS Windows Endpoint Agent Security



\## Purpose



Phase 1O establishes a production-oriented Windows endpoint agent for the IT Support Diagnostic System (ITDS).



The endpoint agent is telemetry-only. It is designed to collect endpoint health information and securely communicate that information to the ITDS API.



\## Security Boundary



The Phase 1O agent does not provide arbitrary endpoint control.



The implementation does not provide:



\* arbitrary command execution

\* arbitrary PowerShell execution

\* `cmd.exe` execution

\* WMI/WMIC-based execution

\* SSH-based endpoint control

\* network scanning

\* repair or destructive operations

\* Windows configuration modification

\* download-and-execute behavior



Operational remediation remains outside the Phase 1O endpoint-agent security boundary.



\## Credential Protection



Agent credentials are protected using Windows DPAPI.



Phase 1O uses machine-scoped DPAPI protection so that the protected credential is associated with the local computer rather than the interactive enrolling user.



Machine-scoped DPAPI must not be interpreted as service-account-only protection.



The security model therefore also depends on filesystem permissions applied to the agent credential storage.



\## Credential Storage



Credential material is stored outside the application source code and outside ordinary plaintext configuration.



The credential storage path is controlled by the agent configuration/path implementation.



The installer applies restrictive NTFS permissions to the protected credential storage so access is limited to the intended runtime identity and required administrative principals.



Credential material must never be written to application logs.



\## Service Identity



The Windows service is intended to run using the least-privilege service identity selected by the Phase 1O deployment implementation.



Normal agent operation must not require an interactive Administrator account.



The service identity and filesystem ACL configuration must be verified during deployment validation.



\## Communication Security



The endpoint communicates with the ITDS API through the existing agent communication client.



The API endpoint must use HTTPS.



Authentication uses the protected agent credential.



Credentials and authorization material must never be exposed through normal diagnostic logging.



Network operations use bounded timeouts and controlled retry behavior.



\## Logging Security



Agent logging is designed to prevent sensitive values from being exposed.



Sensitive values include:



\* agent credentials

\* enrollment tokens

\* bearer tokens

\* authorization headers

\* passwords

\* protected credential contents



Redaction applies both to ordinary string arguments and to non-string values such as exception objects.



\## Enrollment Security



Enrollment establishes the agent identity and credential material required for subsequent authenticated communication.



Enrollment credentials must not be retained in logs or exposed through exception messages.



Credential rotation and credential cleanup must preserve the same secret-handling requirements.



\## Runtime Safety



The service runtime is separated from the endpoint-agent business logic.



The runtime is responsible for controlled lifecycle management and telemetry operation.



The runtime must maintain a single active heartbeat/telemetry loop.



Shutdown must be graceful and must not leave uncontrolled background execution behind.



Network failures must result in controlled runtime behavior rather than arbitrary endpoint actions.



\## Packaging Security



The Phase 1O Windows executable is produced through a reproducible PyInstaller build.



Configuration remains external to the executable.



Secrets and credentials must not be embedded in the source repository or packaged executable.



Generated build output is excluded from source control.



\## Installer Security



The installer is intentionally narrow.



Installation is limited to the ITDS endpoint-agent service and its required files/directories.



The installer does not provide an arbitrary command-execution mechanism.



The uninstaller removes the ITDS agent service and associated deployment resources according to the documented cleanup behavior.



\## Validation Requirements



Before Phase 1O release, the following must be verified:



1\. Windows service registration.

2\. Service startup and graceful shutdown.

3\. Final service identity.

4\. Credential accessibility under the final service identity.

5\. NTFS ACL protection of credential storage.

6\. Credential rotation and deletion.

7\. Installer idempotency.

8\. Deterministic uninstallation.

9\. PyInstaller packaging.

10\. Security-boundary tests.

11\. Logging/redaction tests.

12\. Windows CI validation.



Any item that cannot be demonstrated in the development environment must be recorded as \*\*UNVERIFIED\*\* rather than reported as passed.



\## Security Principle



Phase 1O follows the principle of least privilege and maintains a strict separation between endpoint telemetry collection and endpoint remediation.



The endpoint agent must not become a general-purpose remote execution mechanism.
