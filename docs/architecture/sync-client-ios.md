# Sync Engine - iOS Client Implementation

iOS 26+ Swift implementation guide for the sync engine. See [sync.md](./sync.md) for the protocol specification.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    UI Layer                      │
│                    SwiftUI                       │
├─────────────────────────────────────────────────┤
│               State Management                   │
│           @Observable + SwiftData                │
├─────────────────────────────────────────────────┤
│                 Sync Engine                      │
│     ┌─────────────┬─────────────┬────────────┐  │
│     │ Operation   │ Sync        │ Conflict   │  │
│     │ Queue       │ Scheduler   │ Resolver   │  │
│     │  (Actor)    │  (Actor)    │            │  │
│     └─────────────┴─────────────┴────────────┘  │
├─────────────────────────────────────────────────┤
│               Local Database                     │
│                  SwiftData                       │
└─────────────────────────────────────────────────┘
```

**Key Technologies:**
- **Swift Concurrency** - async/await, actors for thread safety
- **SwiftData** - persistence layer (replaces Core Data)
- **Observation framework** - reactive state management
- **NWPathMonitor** - network state detection
- **BGTaskScheduler** - background sync

---

## Client-Side ID Generation

Use **ULIDs** for time-ordered, collision-resistant IDs:

```swift
import Foundation

enum EntityType: String {
    case timeEntry = "te"
    case project = "prj"
    case contact = "ct"
}

struct IDGenerator {
    static func generate(for entityType: EntityType) -> String {
        "\(entityType.rawValue)_\(ULID.generate())"
    }
}

// ULID implementation (or use a package like swift-ulid)
struct ULID {
    static func generate() -> String {
        let timestamp = UInt64(Date().timeIntervalSince1970 * 1000)
        let randomBytes = (0..<10).map { _ in UInt8.random(in: 0...255) }
        return encodeBase32(timestamp: timestamp, randomness: randomBytes)
    }

    private static func encodeBase32(timestamp: UInt64, randomness: [UInt8]) -> String {
        // Crockford's Base32 encoding
        let alphabet = Array("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        var result = ""

        // Encode 48-bit timestamp (10 chars)
        var ts = timestamp
        for _ in 0..<10 {
            result = String(alphabet[Int(ts & 0x1F)]) + result
            ts >>= 5
        }

        // Encode 80-bit randomness (16 chars)
        var rand = randomness
        for _ in 0..<16 {
            let idx = Int(rand[0] & 0x1F)
            result += String(alphabet[idx])
            for i in 0..<(rand.count - 1) {
                rand[i] = (rand[i] >> 5) | (rand[i + 1] << 3)
            }
            rand[rand.count - 1] >>= 5
        }

        return result
    }
}
```

---

## Persistent Operation Queue

Operations must be persisted to local storage **before** showing success to the user.

```swift
import SwiftData

@Model
final class SyncOperation {
    @Attribute(.unique) var idempotencyKey: String
    var entityType: String
    var entityId: String
    var intent: OperationIntent
    var payload: Data
    var createdAt: Date
    var status: OperationStatus
    var attempts: Int
    var lastError: String?
    var nextRetryAt: Date?

    enum OperationIntent: String, Codable {
        case create, update, delete
    }

    enum OperationStatus: String, Codable {
        case pending, syncing, failed
    }

    init(
        idempotencyKey: String,
        entityType: String,
        entityId: String,
        intent: OperationIntent,
        payload: Data
    ) {
        self.idempotencyKey = idempotencyKey
        self.entityType = entityType
        self.entityId = entityId
        self.intent = intent
        self.payload = payload
        self.createdAt = Date()
        self.status = .pending
        self.attempts = 0
    }
}

actor OperationQueue {
    private let modelContainer: ModelContainer

    init(modelContainer: ModelContainer) {
        self.modelContainer = modelContainer
    }

    func enqueue(_ operation: SyncOperation) async throws {
        let context = ModelContext(modelContainer)
        context.insert(operation)
        try context.save()
    }

    func getPending() async throws -> [SyncOperation] {
        let context = ModelContext(modelContainer)
        let now = Date()

        let predicate = #Predicate<SyncOperation> { op in
            op.status == .pending ||
            (op.status == .failed && op.nextRetryAt != nil && op.nextRetryAt! <= now)
        }

        var descriptor = FetchDescriptor(predicate: predicate)
        descriptor.sortBy = [SortDescriptor(\.createdAt)]
        descriptor.fetchLimit = 100

        return try context.fetch(descriptor)
    }

    func markSynced(_ idempotencyKey: String) async throws {
        let context = ModelContext(modelContainer)
        let predicate = #Predicate<SyncOperation> { $0.idempotencyKey == idempotencyKey }
        try context.delete(model: SyncOperation.self, where: predicate)
        try context.save()
    }

    func scheduleRetry(_ idempotencyKey: String) async throws {
        let context = ModelContext(modelContainer)
        let predicate = #Predicate<SyncOperation> { $0.idempotencyKey == idempotencyKey }
        var descriptor = FetchDescriptor(predicate: predicate)
        descriptor.fetchLimit = 1

        guard let operation = try context.fetch(descriptor).first else { return }

        operation.attempts += 1
        operation.nextRetryAt = SyncRetryPolicy.calculateNextRetry(attempts: operation.attempts)
        operation.status = .failed

        try context.save()
    }

    func markPermanentlyFailed(_ idempotencyKey: String, error: String?) async throws {
        let context = ModelContext(modelContainer)
        let predicate = #Predicate<SyncOperation> { $0.idempotencyKey == idempotencyKey }
        var descriptor = FetchDescriptor(predicate: predicate)
        descriptor.fetchLimit = 1

        guard let operation = try context.fetch(descriptor).first else { return }

        operation.status = .failed
        operation.lastError = error
        operation.nextRetryAt = nil  // No more retries

        try context.save()
    }

    var isEmpty: Bool {
        get async throws {
            let context = ModelContext(modelContainer)
            let predicate = #Predicate<SyncOperation> { $0.status == .pending }
            let descriptor = FetchDescriptor(predicate: predicate)
            return try context.fetchCount(descriptor) == 0
        }
    }
}
```

---

## Retry Logic with Exponential Backoff

```swift
struct SyncRetryPolicy {
    static let maxAttempts = 10
    static let baseDelay: TimeInterval = 1.0
    static let maxDelay: TimeInterval = 300.0  // 5 minutes

    static func calculateNextRetry(attempts: Int) -> Date {
        let delay = min(
            baseDelay * pow(2.0, Double(attempts)),
            maxDelay
        )
        let jitter = delay * 0.2 * Double.random(in: 0...1)
        return Date().addingTimeInterval(delay + jitter)
    }

    static func shouldRetry(attempts: Int, error: SyncError) -> Bool {
        guard attempts < maxAttempts else { return false }
        return error.isRetryable
    }
}

struct SyncError: Error {
    let code: String
    let message: String
    let statusCode: Int?

    var isRetryable: Bool {
        guard let statusCode else { return true }
        if statusCode >= 500 { return true }
        if statusCode == 429 { return true }
        return false
    }

    static let permanentErrorCodes: Set<String> = [
        "PROJECT_ARCHIVED",
        "ENTITY_NOT_FOUND",
        "PERMISSION_DENIED",
        "VALIDATION_ERROR"
    ]

    var isPermanent: Bool {
        Self.permanentErrorCodes.contains(code)
    }
}
```

| Attempt | Base Delay | With Jitter (±20%) |
|---------|------------|-------------------|
| 1 | 1s | 0.8s - 1.2s |
| 2 | 2s | 1.6s - 2.4s |
| 3 | 4s | 3.2s - 4.8s |
| 4 | 8s | 6.4s - 9.6s |
| 5 | 16s | 12.8s - 19.2s |
| 6 | 32s | 25.6s - 38.4s |
| 7 | 64s | 51.2s - 76.8s |
| 8 | 128s | 102.4s - 153.6s |
| 9 | 256s | 204.8s - 307.2s |
| 10 | 300s (capped) | 240s - 360s |

---

## Partial Batch Failure Handling

A batch push may have mixed results—handle each operation independently:

```swift
struct PushResult: Decodable {
    let idempotencyKey: String
    let status: Status
    let errorCode: String?
    let errorMessage: String?

    enum Status: String, Decodable {
        case applied, duplicate, rejected
    }

    enum CodingKeys: String, CodingKey {
        case idempotencyKey = "idempotency_key"
        case status
        case errorCode = "error_code"
        case errorMessage = "error_message"
    }
}

extension SyncEngine {
    func handlePushResults(_ results: [PushResult]) async throws {
        for result in results {
            switch result.status {
            case .applied, .duplicate:
                try await operationQueue.markSynced(result.idempotencyKey)

            case .rejected:
                if let errorCode = result.errorCode,
                   !SyncError.permanentErrorCodes.contains(errorCode) {
                    try await operationQueue.scheduleRetry(result.idempotencyKey)
                } else {
                    try await operationQueue.markPermanentlyFailed(
                        result.idempotencyKey,
                        error: result.errorMessage
                    )
                    await notifyUserOfFailure(result)
                }
            }
        }
    }

    @MainActor
    private func notifyUserOfFailure(_ result: PushResult) {
        // Post notification for UI to display
        NotificationCenter.default.post(
            name: .syncOperationFailed,
            object: nil,
            userInfo: [
                "idempotencyKey": result.idempotencyKey,
                "errorMessage": result.errorMessage ?? "Unknown error"
            ]
        )
    }
}

extension Notification.Name {
    static let syncOperationFailed = Notification.Name("SyncOperationFailed")
}
```

---

## Network State Detection

```swift
import Network

@Observable
final class NetworkMonitor {
    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "NetworkMonitor")

    private(set) var isConnected = true
    private(set) var isExpensive = false  // Cellular
    private(set) var isConstrained = false  // Low Data Mode

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.isConnected = path.status == .satisfied
                self?.isExpensive = path.isExpensive
                self?.isConstrained = path.isConstrained
            }
        }
        monitor.start(queue: queue)
    }

    deinit {
        monitor.cancel()
    }
}

actor NetworkAwareSyncScheduler {
    private let networkMonitor: NetworkMonitor
    private let syncEngine: SyncEngine
    private var syncTask: Task<Void, Never>?
    private var isRunning = false

    init(networkMonitor: NetworkMonitor, syncEngine: SyncEngine) {
        self.networkMonitor = networkMonitor
        self.syncEngine = syncEngine
    }

    func start() {
        guard !isRunning else { return }
        isRunning = true

        syncTask = Task { [weak self] in
            guard let self else { return }

            while !Task.isCancelled {
                if await networkMonitor.isConnected {
                    do {
                        try await syncEngine.sync()
                    } catch {
                        // Log error, will retry on next interval
                    }
                }

                try? await Task.sleep(for: .seconds(30))
            }
        }
    }

    func stop() {
        isRunning = false
        syncTask?.cancel()
        syncTask = nil
    }

    func triggerImmediateSync() async {
        guard networkMonitor.isConnected else { return }
        try? await syncEngine.sync()
    }
}
```

---

## Sync State Machine

```swift
@Observable
final class SyncEngine {
    enum State: Equatable {
        case idle
        case pushing(batchSize: Int)
        case pulling(cursor: String?)
        case error(message: String, retryAt: Date)
    }

    private(set) var state: State = .idle
    private(set) var lastPullAt: Date?

    let operationQueue: OperationQueue
    private let apiClient: SyncAPIClient
    private let modelContainer: ModelContainer
    private let cursorManager = SyncCursorManager()

    init(
        operationQueue: OperationQueue,
        apiClient: SyncAPIClient,
        modelContainer: ModelContainer
    ) {
        self.operationQueue = operationQueue
        self.apiClient = apiClient
        self.modelContainer = modelContainer
    }

    func sync() async throws {
        guard state == .idle else { return }

        // Push first (client changes take priority)
        try await pushPendingOperations()

        // ALWAYS pull after push, regardless of queue state
        try await pullChanges()
    }

    private func pushPendingOperations() async throws {
        let pending = try await operationQueue.getPending()
        guard !pending.isEmpty else { return }

        state = .pushing(batchSize: pending.count)
        defer { state = .idle }

        let request = SyncPushRequest(operations: pending.map(\.toAPIOperation))
        let results = try await apiClient.push(request)
        try await handlePushResults(results)
    }

    private func pullChanges() async throws {
        let cursor = await cursorManager.cursor
        state = .pulling(cursor: cursor)
        defer { state = .idle }

        try await pullWithRecovery()
    }

    /// Check if client has pending local changes.
    var hasPendingChanges: Bool {
        get async {
            (try? await operationQueue.isEmpty) == false
        }
    }

    /// Check if client is likely in sync with server.
    var isLikelySynced: Bool {
        get async {
            guard let lastPullAt,
                  state == .idle,
                  Date().timeIntervalSince(lastPullAt) < 60 else {
                return false
            }
            return await !hasPendingChanges
        }
    }
}
```

---

## Pull Failure Recovery

```swift
actor SyncCursorManager {
    private let key = "sync_cursor"
    private let defaults = UserDefaults.standard

    var cursor: String? {
        defaults.string(forKey: key)
    }

    func setCursor(_ cursor: String) {
        defaults.set(cursor, forKey: key)
    }

    func resetCursor() {
        defaults.removeObject(forKey: key)
    }
}

extension SyncEngine {
    func pullWithRecovery() async throws {
        let cursor = await cursorManager.cursor

        do {
            let response = try await apiClient.pull(cursor: cursor)

            // Apply changes in transaction
            let context = ModelContext(modelContainer)
            for change in response.changes {
                try applyChange(change, context: context)
            }
            try context.save()

            // Only update cursor after successful apply
            await cursorManager.setCursor(response.cursor)
            lastPullAt = Date()

            // Continue if more pages available
            if response.hasMore {
                try await pullWithRecovery()
            }

        } catch let error as SyncError where error.code == "CURSOR_INVALID" {
            await cursorManager.resetCursor()
            try await clearLocalData()
            try await pullWithRecovery()
        }
    }

    private func applyChange(_ change: SyncChange, context: ModelContext) throws {
        // Entity-specific application logic
        switch change.entityType {
        case "contact":
            try applyContactChange(change, context: context)
        case "time_entry":
            try applyTimeEntryChange(change, context: context)
        default:
            break
        }
    }

    private func clearLocalData() async throws {
        let context = ModelContext(modelContainer)
        try context.delete(model: Contact.self)
        try context.delete(model: TimeEntry.self)
        try context.save()
    }
}
```

---

## Full Re-Sync Handling

```swift
extension SyncEngine {
    private static let schemaVersion = 3
    private static let schemaVersionKey = "sync_schema_version"
    private static let fullSyncInterval: TimeInterval = 24 * 60 * 60  // 24 hours

    func initialize() async throws {
        let storedVersion = UserDefaults.standard.integer(forKey: Self.schemaVersionKey)

        if storedVersion != Self.schemaVersion {
            try await triggerFullResync(reason: "schema_upgrade")
            UserDefaults.standard.set(Self.schemaVersion, forKey: Self.schemaVersionKey)
        }
    }

    func triggerFullResync(reason: String) async throws {
        // Clear cursor - next pull starts from beginning
        await cursorManager.resetCursor()

        // Clear local data
        try await clearLocalData()

        // Pull everything
        try await pullWithRecovery()
    }

    func handlePullResponse(_ response: SyncPullResponse) async throws {
        if response.forceResync {
            try await triggerFullResync(reason: "server_requested")
            return
        }

        // Normal processing...
    }
}
```

---

## Background Sync with BGTaskScheduler

```swift
import BackgroundTasks

extension SyncEngine {
    static let backgroundTaskIdentifier = "com.app.sync.refresh"

    static func registerBackgroundTask() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: backgroundTaskIdentifier,
            using: nil
        ) { task in
            handleBackgroundSync(task: task as! BGAppRefreshTask)
        }
    }

    static func scheduleBackgroundSync() {
        let request = BGAppRefreshTaskRequest(identifier: backgroundTaskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)  // 15 min

        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            // Log scheduling failure
        }
    }

    private static func handleBackgroundSync(task: BGAppRefreshTask) {
        // Schedule next sync
        scheduleBackgroundSync()

        let syncTask = Task {
            do {
                let engine = await SyncEngine.shared
                try await engine.sync()
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }

        task.expirationHandler = {
            syncTask.cancel()
        }
    }
}
```

---

## Push Notification Nudge Handling

Handle silent push notifications from the server to trigger immediate sync:

```swift
import UserNotifications

extension AppDelegate {
    func application(
        _ application: UIApplication,
        didReceiveRemoteNotification userInfo: [AnyHashable: Any],
        fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        guard let type = userInfo["type"] as? String, type == "sync_nudge" else {
            completionHandler(.noData)
            return
        }

        Task {
            do {
                try await SyncEngine.shared.sync()
                completionHandler(.newData)
            } catch {
                completionHandler(.failed)
            }
        }
    }
}
```

---

## API Client

```swift
protocol SyncAPIClient: Sendable {
    func push(_ request: SyncPushRequest) async throws -> [PushResult]
    func pull(cursor: String?) async throws -> SyncPullResponse
}

struct SyncPushRequest: Encodable {
    let operations: [SyncOperationDTO]
}

struct SyncOperationDTO: Encodable {
    let idempotencyKey: String
    let entityType: String
    let entityId: String
    let intent: String
    let data: [String: AnyCodable]
    let clientTimestamp: String

    enum CodingKeys: String, CodingKey {
        case idempotencyKey = "idempotency_key"
        case entityType = "entity_type"
        case entityId = "entity_id"
        case intent
        case data
        case clientTimestamp = "client_timestamp"
    }
}

struct SyncPullResponse: Decodable {
    let changes: [SyncChange]
    let cursor: String
    let hasMore: Bool
    let forceResync: Bool?

    enum CodingKeys: String, CodingKey {
        case changes
        case cursor
        case hasMore = "has_more"
        case forceResync = "force_resync"
    }
}

struct SyncChange: Decodable {
    let entityType: String
    let entityId: String
    let operation: String
    let data: [String: AnyCodable]?
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case entityType = "entity_type"
        case entityId = "entity_id"
        case operation
        case data
        case updatedAt = "updated_at"
    }
}
```

---

## Reliability Guarantees Summary

| Scenario | Guarantee |
|----------|-----------|
| App crashes after user action | Operation persisted in SwiftData, synced on restart |
| Network fails mid-push | Retried with exponential backoff |
| 3/10 operations rejected | Each handled independently |
| Server returns 500 | Retried up to 10 times over ~5 hours |
| Validation error (4xx) | Marked failed, user notified |
| Cursor becomes invalid | Full re-sync triggered |
| App backgrounded | BGTaskScheduler continues sync |
| Silent push received | Immediate sync triggered |
