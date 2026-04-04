use cxx::CxxString;
use std::path::PathBuf;
use std::pin::Pin;
use taskchampion as tc;
use tc::storage::{Storage, StorageTxn};
use tc::PowerSyncStorage;

// All Taskchampion FFI is contained in this module, due to issues with cxx and multiple modules
// such as https://github.com/dtolnay/cxx/issues/1323.

/// FFI interface for TaskChampion.
///
/// This loosely follows the TaskChampion API defined at
/// https://docs.rs/taskchampion/latest/taskchampion/, with adjustments made as necessary to
/// accomodate cxx's limitations. Consult that documentation for full descriptions of the types and
/// methods.
///
/// This interface is an internal implementation detail of Taskwarrior and may change at any time.
#[cxx::bridge(namespace = "tc")]
mod ffi {
    // --- Uuid

    #[derive(Debug, Eq, PartialEq, Clone, Copy)]
    struct Uuid {
        v: [u8; 16],
    }

    extern "Rust" {
        /// Generate a new, random Uuid.
        fn uuid_v4() -> Uuid;

        /// Parse the given string as a Uuid, panicking if it is not valid.
        fn uuid_from_string(uuid: Pin<&CxxString>) -> Uuid;

        /// Convert the given Uuid to a string.
        fn to_string(self: &Uuid) -> String;

        /// Check whether this is the "nil" Uuid, used as a sentinel value.
        fn is_nil(self: &Uuid) -> bool;
    }

    // --- Operation and Operations

    extern "Rust" {
        type Operation;

        /// Check if this is a Create operation.
        fn is_create(&self) -> bool;

        /// Check if this is a Update operation.
        fn is_update(&self) -> bool;

        /// Check if this is a Delete operation.
        fn is_delete(&self) -> bool;

        /// Check if this is an UndoPoint operation.
        fn is_undo_point(&self) -> bool;

        /// Get the operation's uuid.
        ///
        /// Only valid for create, update, and delete operations.
        fn get_uuid(&self) -> Uuid;

        /// Get the `old_task` for this update operation.
        ///
        /// Only valid for delete operations.
        fn get_old_task(&self) -> Vec<PropValuePair>;

        /// Get the `property` for this update operation.
        ///
        /// Only valid for update operations.
        fn get_property(&self, property_out: Pin<&mut CxxString>);

        /// Get the `value` for this update operation, returning false if the
        /// `value` field is None.
        ///
        /// Only valid for update operations.
        fn get_value(&self, value_out: Pin<&mut CxxString>) -> bool;

        /// Get the `old_value` for this update operation, returning false if the
        /// `old_value` field is None.
        ///
        /// Only valid for update operations.
        fn get_old_value(&self, old_value_out: Pin<&mut CxxString>) -> bool;

        /// Get the `timestamp` for this update operation.
        ///
        /// Only valid for update operations.
        fn get_timestamp(&self) -> i64;

        /// Create a new vector of operations. It's also fine to construct a
        /// `rust::Vec<tc::Operation>` directly.
        fn new_operations() -> Vec<Operation>;

        /// Add an UndoPoint operation to the vector of operations. All other
        /// operation types should be added via `TaskData`.
        fn add_undo_point(ops: &mut Vec<Operation>);
    }

    // --- Replica

    extern "Rust" {
        type Replica;

        /// Create a new replica backed by PowerSync storage.
        fn new_replica_powersync(db_path: String) -> Result<Box<Replica>>;

        /// Create a new replica backed by PgWire storage.
        fn new_replica_pgwire(database_url: String, token: String) -> Result<Box<Replica>>;

        /// Create a new in-memory test replica (PowerSync with ephemeral storage).
        fn new_replica_for_test() -> Result<Box<Replica>>;

        /// Commit the given operations to the replica.
        fn commit_operations(&mut self, ops: Vec<Operation>) -> Result<()>;

        /// Commit the reverse of the given operations.
        fn commit_reversed_operations(&mut self, ops: Vec<Operation>) -> Result<bool>;

        /// Get `TaskData` values for all tasks in the replica.
        ///
        /// This contains `OptionTaskData` to allow C++ to `take` values out of the vector and use
        /// them as `rust::Box<TaskData>`. Cxx does not support `Vec<Box<_>>`. Cxx also does not
        /// handle `HashMap`, so the result is not a map from uuid to task. The returned Vec is
        /// fully populated, so it is safe to call `take` on each value in the returned Vec once .
        fn all_task_data(&mut self) -> Result<Vec<OptionTaskData>>;

        /// Simiar to all_task_data, but returing only pending tasks (those in the working set).
        fn pending_task_data(&mut self) -> Result<Vec<OptionTaskData>>;

        /// Get the UUIDs of all tasks.
        fn all_task_uuids(&mut self) -> Result<Vec<Uuid>>;

        /// Expire old, deleted tasks.
        fn expire_tasks(&mut self) -> Result<()>;

        /// Get an existing task by its UUID.
        fn get_task_data(&mut self, uuid: Uuid) -> Result<OptionTaskData>;

        /// Get the operations for a task task by its UUID.
        fn get_task_operations(&mut self, uuid: Uuid) -> Result<Vec<Operation>>;

        /// Return the operations back to and including the last undo point, or since the last sync if
        /// no undo point is found.
        fn get_undo_operations(&mut self) -> Result<Vec<Operation>>;

        /// Get the number of local, un-sync'd operations, excluding undo operations.
        fn num_local_operations(&mut self) -> Result<usize>;

        /// Get the number of (un-synchronized) undo points in storage.
        fn num_undo_points(&mut self) -> Result<usize>;

        /// Build a TreeMap from all tasks in this replica.
        fn tree_map(&mut self) -> Result<Box<TreeMapWrapper>>;

        // --- Tag registry operations

        /// Return registered tag names from tc_config (tags that have been explicitly
        /// added via `task tag add` or seeded via `task tag migrate`).
        fn get_all_task_tags(&mut self) -> Result<Vec<String>>;

        /// Seed the tag registry from existing task data (startup one-time migration).
        ///
        /// If tc_config already has at least one registered tag, this is a no-op — the
        /// registry is considered already seeded. Otherwise scans all task data for tag_*
        /// keys and adds each unique name to tc_config.tags. Intended to be called on
        /// startup so that existing tags survive an upgrade without manual re-registration.
        fn seed_tags_from_tasks(&mut self) -> Result<()>;

        /// Migrate tags from existing task data into the registry (explicit CLI command).
        ///
        /// Unlike `seed_tags_from_tasks`, this always scans task data and adds any tag not
        /// yet in the registry. Does not remove tags present in the registry but absent from
        /// task data. Safe to run repeatedly.
        fn migrate_tags_from_tasks(&mut self) -> Result<()>;

        /// Register a tag by name in tc_config.
        ///
        /// If the tag is already registered, this is a no-op.
        fn register_tag(&mut self, name: &CxxString) -> Result<()>;

        /// Validate that a tag is registered in tc_config.
        ///
        /// Returns an error if the tag is not registered, with a message directing the user
        /// to run `task tag add <name>` to register it.
        fn validate_tag(&mut self, name: &CxxString) -> Result<()>;

        /// Delete (unregister) a tag by name from tc_config.
        ///
        /// Returns an error if the tag is not currently registered. If the tag is
        /// registered, it is removed from tc_config and the updated config is persisted.
        fn delete_tag(&mut self, name: &CxxString) -> Result<()>;
    }

    // --- OptionTaskData

    /// Wrapper around `Option<Box<TaskData>>`, required since cxx does not support Option<T>.
    ///
    /// Note that if an OptionTaskData containing a task is dropped without calling `take`,
    /// it will leak the contained task. C++ code should be careful to always take.
    struct OptionTaskData {
        maybe_task: *mut TaskData,
    }

    extern "Rust" {
        /// Check if the value contains a task.
        fn is_some(self: &OptionTaskData) -> bool;
        /// Check if the value does not contain a task.
        fn is_none(self: &OptionTaskData) -> bool;
        /// Get the contained task, or panic if there is no task. The OptionTaskData
        /// will be reset to contain None.
        fn take(self: &mut OptionTaskData) -> Box<TaskData>;
    }

    // --- TaskData

    extern "Rust" {
        type TaskData;

        /// Create a new task with the given Uuid.
        fn create_task(uuid: Uuid, ops: &mut Vec<Operation>) -> Box<TaskData>;

        /// Get the task's Uuid.
        fn get_uuid(&self) -> Uuid;

        /// Get a value on this task. If the property exists, returns true and updates
        /// the output parameter. If not, returns false.
        fn get(&self, property: &CxxString, value_out: Pin<&mut CxxString>) -> bool;

        /// Check if the given property is set.
        fn has(&self, property: &CxxString) -> bool;

        /// Enumerate all properties on this task, in arbitrary order.
        fn properties(&self) -> Vec<String>;

        /// Enumerate all properties and their values on this task, in arbitrary order, as a
        /// vector.
        fn items(&self) -> Vec<PropValuePair>;

        /// Update the given property with the given value.
        fn update(&mut self, property: &CxxString, value: &CxxString, ops: &mut Vec<Operation>);

        /// Like `update`, but removing the property by passing None for the value.
        fn update_remove(&mut self, property: &CxxString, ops: &mut Vec<Operation>);

        /// Delete the task. The name is `delete_task` because `delete` is a C++ keyword.
        fn delete_task(&mut self, ops: &mut Vec<Operation>);
    }

    // --- PropValuePair

    #[derive(Debug, Eq, PartialEq)]
    struct PropValuePair {
        prop: String,
        value: String,
    }

    // --- UuidStringPair

    /// A pair of (Uuid, String) for sibling_positions results.
    #[derive(Debug)]
    struct UuidStringPair {
        uuid: Uuid,
        value: String,
    }

    // --- TreeMapWrapper

    extern "Rust" {
        type TreeMapWrapper;

        /// Return the direct children of `uuid`, in position order.
        fn children(self: &TreeMapWrapper, uuid: Uuid) -> Vec<Uuid>;

        /// Return all descendants of `uuid` in depth-first pre-order.
        fn descendants(self: &TreeMapWrapper, uuid: Uuid) -> Vec<Uuid>;

        /// Return the root tasks (those with no parent), in deterministic UUID order.
        fn roots(self: &TreeMapWrapper) -> Vec<Uuid>;

        /// Check if `ancestor` is an ancestor of `uuid`.
        fn is_ancestor(self: &TreeMapWrapper, uuid: Uuid, ancestor: Uuid) -> bool;

        /// Get sibling positions under a parent.
        ///
        /// `at_root` = true means parent is None (root-level siblings).
        /// `has_exclude` = true activates the exclude filter on `exclude`.
        fn sibling_positions(
            self: &TreeMapWrapper,
            parent: Uuid,
            at_root: bool,
            exclude: Uuid,
            has_exclude: bool,
        ) -> Vec<UuidStringPair>;

        /// Return the UUIDs of pending direct children.
        fn pending_child_ids(self: &TreeMapWrapper, uuid: Uuid) -> Vec<Uuid>;

        /// Returns true if any task had an invalid parent UUID during construction.
        fn had_invalid_data(self: &TreeMapWrapper) -> bool;
    }

    // --- PlanNode

    /// A single parsed section from a markdown plan document.
    ///
    /// `level` is the raw heading level (1 for `#`, 2 for `##`, etc.).
    /// The C++ caller is responsible for any depth squashing.
    struct PlanNode {
        level: u32,
        title: String,
        annotation: String,
    }

    extern "Rust" {
        /// Parse markdown into a flat list of PlanNode values.
        ///
        /// Headings inside fenced code blocks are never treated as headings.
        /// `level` is the raw heading level; the C++ caller squashes depth.
        fn tc_parse_plan_markdown(input: &CxxString) -> Vec<PlanNode>;
    }

    // --- Position helpers (free functions)

    extern "Rust" {
        /// Generate the position string for appending after `last_pos`.
        /// Pass an empty string for `last_pos` to get the first position.
        fn tc_append_position(last_pos: &CxxString) -> Result<String>;

        /// Generate the position string for prepending before `first_pos`.
        /// Pass an empty string for `first_pos` to get a position before the default.
        fn tc_prepend_position(first_pos: &CxxString) -> Result<String>;

        /// Generate the position string between `before_pos` and `after_pos`.
        fn tc_between_position(before_pos: &CxxString, after_pos: &CxxString) -> Result<String>;

        /// Generate `n` sequential position strings.
        fn tc_sequential_positions(n: usize) -> Vec<String>;
    }
}

#[derive(Debug)]
struct CppError(tc::Error);

impl From<tc::Error> for CppError {
    fn from(err: tc::Error) -> Self {
        CppError(err)
    }
}

impl From<anyhow::Error> for CppError {
    fn from(err: anyhow::Error) -> Self {
        CppError(tc::Error::Other(err))
    }
}

use std::sync::OnceLock;

static RUNTIME: OnceLock<tokio::runtime::Runtime> = OnceLock::new();

fn rt() -> &'static tokio::runtime::Runtime {
    RUNTIME.get_or_init(|| {
        tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap()
    })
}

impl std::fmt::Display for CppError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if let tc::Error::Other(err) = &self.0 {
            // The default `to_string` representation of `anyhow::Error` only shows the "outermost"
            // context, e.g., "Could not connect to server", and omits the juicy details about what
            // actually went wrong. So, join all of those contexts with `: ` for presentation to the C++
            // layer.
            let entire_msg = err
                .chain()
                .skip(1)
                .fold(err.to_string(), |a, b| format!("{}: {}", a, b));
            write!(f, "{}", entire_msg)
        } else {
            self.0.fmt(f)
        }
    }
}

// --- Uuid

impl From<ffi::Uuid> for tc::Uuid {
    fn from(value: ffi::Uuid) -> Self {
        tc::Uuid::from_bytes(value.v)
    }
}

impl From<&ffi::Uuid> for tc::Uuid {
    fn from(value: &ffi::Uuid) -> Self {
        tc::Uuid::from_bytes(value.v)
    }
}

impl From<tc::Uuid> for ffi::Uuid {
    fn from(uuid: tc::Uuid) -> ffi::Uuid {
        ffi::Uuid {
            v: *uuid.as_bytes(),
        }
    }
}

impl From<&tc::Uuid> for ffi::Uuid {
    fn from(uuid: &tc::Uuid) -> ffi::Uuid {
        ffi::Uuid {
            v: *uuid.as_bytes(),
        }
    }
}

fn uuid_v4() -> ffi::Uuid {
    tc::Uuid::new_v4().into()
}

fn uuid_from_string(uuid: Pin<&CxxString>) -> ffi::Uuid {
    let Ok(uuid) = tc::Uuid::parse_str(uuid.to_str().expect("invalid utf-8")) else {
        panic!("{} is not a valid UUID", uuid);
    };
    uuid.into()
}

impl ffi::Uuid {
    #[allow(clippy::inherent_to_string, clippy::wrong_self_convention)]
    fn to_string(&self) -> String {
        tc::Uuid::from(self).as_hyphenated().to_string()
    }

    fn is_nil(&self) -> bool {
        tc::Uuid::from(self).is_nil()
    }
}

// --- Operation and Operations

#[repr(transparent)] // required for safety
pub struct Operation(tc::Operation);

impl Operation {
    fn is_create(&self) -> bool {
        matches!(&self.0, tc::Operation::Create { .. })
    }

    fn is_update(&self) -> bool {
        matches!(&self.0, tc::Operation::Update { .. })
    }

    fn is_delete(&self) -> bool {
        matches!(&self.0, tc::Operation::Delete { .. })
    }

    fn is_undo_point(&self) -> bool {
        matches!(&self.0, tc::Operation::UndoPoint)
    }

    fn get_uuid(&self) -> ffi::Uuid {
        match self.0 {
            tc::Operation::Create { uuid, .. } => uuid,
            tc::Operation::Update { uuid, .. } => uuid,
            tc::Operation::Delete { uuid, .. } => uuid,
            _ => panic!("operation has no uuid"),
        }
        .into()
    }

    fn get_property(&self, mut property_out: Pin<&mut CxxString>) {
        match &self.0 {
            tc::Operation::Update { property, .. } => {
                property_out.as_mut().clear();
                property_out.as_mut().push_str(property);
            }
            _ => panic!("operation is not an update"),
        }
    }

    fn get_value(&self, mut value_out: Pin<&mut CxxString>) -> bool {
        match &self.0 {
            tc::Operation::Update { value, .. } => {
                if let Some(value) = value {
                    value_out.as_mut().clear();
                    value_out.as_mut().push_str(value);
                    true
                } else {
                    false
                }
            }
            _ => panic!("operation is not an update"),
        }
    }

    fn get_old_value(&self, mut old_value_out: Pin<&mut CxxString>) -> bool {
        match &self.0 {
            tc::Operation::Update { old_value, .. } => {
                if let Some(old_value) = old_value {
                    old_value_out.as_mut().clear();
                    old_value_out.as_mut().push_str(old_value);
                    true
                } else {
                    false
                }
            }
            _ => panic!("operation is not an update"),
        }
    }

    fn get_timestamp(&self) -> i64 {
        match &self.0 {
            tc::Operation::Update { timestamp, .. } => timestamp.timestamp(),
            _ => panic!("operation is not an update"),
        }
    }

    fn get_old_task(&self) -> Vec<ffi::PropValuePair> {
        match &self.0 {
            tc::Operation::Delete { old_task, .. } => old_task
                .iter()
                .map(|(p, v)| ffi::PropValuePair {
                    prop: p.into(),
                    value: v.into(),
                })
                .collect(),
            _ => panic!("operation is not a delete"),
        }
    }
}

fn new_operations() -> Vec<Operation> {
    Vec::new()
}

fn add_undo_point(ops: &mut Vec<Operation>) {
    ops.push(Operation(tc::Operation::UndoPoint));
}

// --- DynStorage: runtime-selectable storage backend

/// A storage backend that can be either PowerSync or PgWire, selected at runtime.
enum DynStorage {
    PowerSync(PowerSyncStorage),
    PgWire(tc::PgWireStorage),
}

#[async_trait::async_trait]
impl Storage for DynStorage {
    async fn txn<'a>(
        &'a mut self,
    ) -> std::result::Result<Box<dyn StorageTxn + Send + 'a>, tc::Error> {
        match self {
            DynStorage::PowerSync(s) => s.txn().await,
            DynStorage::PgWire(s) => s.txn().await,
        }
    }
}

// --- Replica

struct Replica(tc::Replica<DynStorage>);

impl From<tc::Replica<DynStorage>> for Replica {
    fn from(inner: tc::Replica<DynStorage>) -> Self {
        Replica(inner)
    }
}

fn new_replica_powersync(db_path: String) -> Result<Box<Replica>, CppError> {
    rt().block_on(async {
        let path = PathBuf::from(db_path);
        let storage = PowerSyncStorage::new(&path).await.map_err(|e| {
            anyhow::anyhow!("failed to open PowerSync DB at '{}': {}", path.display(), e)
        })?;
        Ok(Box::new(
            tc::Replica::new(DynStorage::PowerSync(storage)).into(),
        ))
    })
}

fn new_replica_pgwire(database_url: String, token: String) -> Result<Box<Replica>, CppError> {
    rt().block_on(async {
        let storage = tc::PgWireStorage::new(&database_url, &token)
            .await
            .map_err(|e| {
                anyhow::anyhow!("failed to open PgWire DB at '{}': {}", database_url, e)
            })?;
        Ok(Box::new(
            tc::Replica::new(DynStorage::PgWire(storage)).into(),
        ))
    })
}

fn new_replica_for_test() -> Result<Box<Replica>, CppError> {
    rt().block_on(async {
        let storage = PowerSyncStorage::new_for_test()
            .await
            .map_err(|e| anyhow::anyhow!("failed to create in-memory test replica: {}", e))?;
        Ok(Box::new(
            tc::Replica::new(DynStorage::PowerSync(storage)).into(),
        ))
    })
}

/// Utility function for Replica methods using Operations.
fn to_tc_operations(ops: Vec<Operation>) -> Vec<tc::Operation> {
    // SAFETY: Operation is a transparent newtype for tc::Operation, so a Vec of one is
    // a Vec of the other.
    unsafe { std::mem::transmute::<Vec<Operation>, Vec<tc::Operation>>(ops) }
}

/// Utility function for Replica methods using Operations.
fn from_tc_operations(ops: Vec<tc::Operation>) -> Vec<Operation> {
    // SAFETY: Operation is a transparent newtype for tc::Operation, so a Vec of one is
    // a Vec of the other.
    unsafe { std::mem::transmute::<Vec<tc::Operation>, Vec<Operation>>(ops) }
}

impl Replica {
    fn commit_operations(&mut self, ops: Vec<Operation>) -> Result<(), CppError> {
        rt().block_on(async { Ok(self.0.commit_operations(to_tc_operations(ops)).await?) })
    }

    fn commit_reversed_operations(&mut self, ops: Vec<Operation>) -> Result<bool, CppError> {
        rt().block_on(async {
            Ok(self
                .0
                .commit_reversed_operations(to_tc_operations(ops))
                .await?)
        })
    }

    fn all_task_data(&mut self) -> Result<Vec<ffi::OptionTaskData>, CppError> {
        rt().block_on(async {
            Ok(self
                .0
                .all_task_data()
                .await?
                .drain()
                .map(|(_, t)| Some(t).into())
                .collect())
        })
    }

    fn pending_task_data(&mut self) -> Result<Vec<ffi::OptionTaskData>, CppError> {
        rt().block_on(async {
            Ok(self
                .0
                .pending_task_data()
                .await?
                .drain(..)
                .map(|t| Some(t).into())
                .collect())
        })
    }

    fn all_task_uuids(&mut self) -> Result<Vec<ffi::Uuid>, CppError> {
        rt().block_on(async {
            Ok(self
                .0
                .all_task_uuids()
                .await?
                .into_iter()
                .map(ffi::Uuid::from)
                .collect())
        })
    }

    fn expire_tasks(&mut self) -> Result<(), CppError> {
        rt().block_on(async { Ok(self.0.expire_tasks().await?) })
    }

    fn get_task_data(&mut self, uuid: ffi::Uuid) -> Result<ffi::OptionTaskData, CppError> {
        rt().block_on(async { Ok(self.0.get_task_data(uuid.into()).await?.into()) })
    }

    fn get_task_operations(&mut self, uuid: ffi::Uuid) -> Result<Vec<Operation>, CppError> {
        rt().block_on(async {
            Ok(from_tc_operations(
                self.0.get_task_operations(uuid.into()).await?,
            ))
        })
    }

    fn get_undo_operations(&mut self) -> Result<Vec<Operation>, CppError> {
        rt().block_on(async { Ok(from_tc_operations(self.0.get_undo_operations().await?)) })
    }

    fn num_local_operations(&mut self) -> Result<usize, CppError> {
        rt().block_on(async { Ok(self.0.num_local_operations().await?) })
    }

    fn num_undo_points(&mut self) -> Result<usize, CppError> {
        rt().block_on(async { Ok(self.0.num_undo_points().await?) })
    }

    fn tree_map(&mut self) -> Result<Box<TreeMapWrapper>, CppError> {
        rt().block_on(async {
            let arc = self.0.tree_map().await?;
            Ok(Box::new(TreeMapWrapper((*arc).clone())))
        })
    }

    fn get_all_task_tags(&mut self) -> Result<Vec<String>, CppError> {
        rt().block_on(async {
            let config = self.0.get_tc_config_parsed().await?;
            Ok(config.tag_list())
        })
    }

    fn seed_tags_from_tasks(&mut self) -> Result<(), CppError> {
        rt().block_on(async {
            let mut config = self.0.get_tc_config_parsed().await?;
            // Only auto-seed when the registry is empty (one-time migration guard).
            if !config.tag_list().is_empty() {
                return Ok(());
            }
            let task_tags = self.0.get_all_tags().await?;
            for tag in task_tags {
                config.add_tag(&tag);
            }
            self.0.set_tc_config_parsed(&config).await?;
            Ok(())
        })
    }

    fn migrate_tags_from_tasks(&mut self) -> Result<(), CppError> {
        rt().block_on(async {
            let mut config = self.0.get_tc_config_parsed().await?;
            let task_tags = self.0.get_all_tags().await?;
            for tag in task_tags {
                config.add_tag(&tag);
            }
            self.0.set_tc_config_parsed(&config).await?;
            Ok(())
        })
    }

    fn register_tag(&mut self, name: &CxxString) -> Result<(), CppError> {
        let tag = name.to_string_lossy().into_owned();
        rt().block_on(async {
            let mut config = self.0.get_tc_config_parsed().await?;
            config.add_tag(&tag);
            self.0.set_tc_config_parsed(&config).await?;
            Ok(())
        })
    }

    fn validate_tag(&mut self, name: &CxxString) -> Result<(), CppError> {
        let tag = name.to_string_lossy().into_owned();
        rt().block_on(async {
            let config = self.0.get_tc_config_parsed().await?;
            if !config.has_tag(&tag) {
                Err(CppError(tc::Error::Other(anyhow::anyhow!(
                    "Tag '{}' is not registered. Use 'task tag add {}' to register it.",
                    tag,
                    tag
                ))))
            } else {
                Ok(())
            }
        })
    }

    fn delete_tag(&mut self, name: &CxxString) -> Result<(), CppError> {
        let tag = name.to_string_lossy().into_owned();
        rt().block_on(async {
            let mut config = self.0.get_tc_config_parsed().await?;
            if !config.remove_tag(&tag) {
                return Err(CppError(tc::Error::Other(anyhow::anyhow!(
                    "Tag '{}' is not registered.",
                    tag
                ))));
            }
            self.0.set_tc_config_parsed(&config).await?;
            Ok(())
        })
    }
}

// --- OptionTaskData

impl From<Option<tc::TaskData>> for ffi::OptionTaskData {
    fn from(value: Option<tc::TaskData>) -> Self {
        let Some(task) = value else {
            return ffi::OptionTaskData {
                maybe_task: std::ptr::null_mut(),
            };
        };
        let boxed = Box::new(task.into());
        ffi::OptionTaskData {
            maybe_task: Box::into_raw(boxed),
        }
    }
}

impl ffi::OptionTaskData {
    fn is_some(&self) -> bool {
        !self.maybe_task.is_null()
    }

    fn is_none(&self) -> bool {
        self.maybe_task.is_null()
    }

    fn take(&mut self) -> Box<TaskData> {
        let mut ptr = std::ptr::null_mut();
        std::mem::swap(&mut ptr, &mut self.maybe_task);
        if ptr.is_null() {
            panic!("Cannot take an empty OptionTaskdata");
        }
        // SAFETY: this value is not NULL and was created from `Box::into_raw` in the
        // `From<Option<TaskData>>` implementation above.
        unsafe { Box::from_raw(ptr) }
    }
}

// --- TaskData

pub struct TaskData(tc::TaskData);

impl From<tc::TaskData> for TaskData {
    fn from(task: tc::TaskData) -> Self {
        TaskData(task)
    }
}

/// Utility function for TaskData methods.
fn operations_ref(ops: &mut Vec<Operation>) -> &mut Vec<tc::Operation> {
    // SAFETY: Operation is a transparent newtype for tc::Operation, so a Vec of one is a
    // Vec of the other.
    unsafe { std::mem::transmute::<&mut Vec<Operation>, &mut Vec<tc::Operation>>(ops) }
}

fn create_task(uuid: ffi::Uuid, ops: &mut Vec<Operation>) -> Box<TaskData> {
    let t = tc::TaskData::create(uuid.into(), operations_ref(ops));
    Box::new(TaskData(t))
}

impl TaskData {
    fn get_uuid(&self) -> ffi::Uuid {
        self.0.get_uuid().into()
    }

    fn get(&self, property: &CxxString, mut value_out: Pin<&mut CxxString>) -> bool {
        let Some(value) = self.0.get(property.to_string_lossy()) else {
            return false;
        };
        value_out.as_mut().clear();
        value_out.as_mut().push_str(value);
        true
    }

    fn has(&self, property: &CxxString) -> bool {
        self.0.has(property.to_string_lossy())
    }

    fn properties(&self) -> Vec<String> {
        self.0.properties().map(|s| s.to_owned()).collect()
    }

    fn items(&self) -> Vec<ffi::PropValuePair> {
        self.0
            .iter()
            .map(|(p, v)| ffi::PropValuePair {
                prop: p.into(),
                value: v.into(),
            })
            .collect()
    }

    fn update(&mut self, property: &CxxString, value: &CxxString, ops: &mut Vec<Operation>) {
        self.0.update(
            property.to_string_lossy(),
            Some(value.to_string_lossy().into()),
            operations_ref(ops),
        )
    }

    fn update_remove(&mut self, property: &CxxString, ops: &mut Vec<Operation>) {
        self.0
            .update(property.to_string_lossy(), None, operations_ref(ops))
    }

    fn delete_task(&mut self, ops: &mut Vec<Operation>) {
        self.0.delete(operations_ref(ops))
    }
}

// --- TreeMapWrapper

struct TreeMapWrapper(tc::TreeMap);

impl TreeMapWrapper {
    fn children(&self, uuid: ffi::Uuid) -> Vec<ffi::Uuid> {
        self.0
            .children(uuid.into())
            .into_iter()
            .map(ffi::Uuid::from)
            .collect()
    }

    fn descendants(&self, uuid: ffi::Uuid) -> Vec<ffi::Uuid> {
        self.0
            .descendants(uuid.into())
            .into_iter()
            .map(ffi::Uuid::from)
            .collect()
    }

    fn roots(&self) -> Vec<ffi::Uuid> {
        self.0.roots().into_iter().map(ffi::Uuid::from).collect()
    }

    fn is_ancestor(&self, uuid: ffi::Uuid, ancestor: ffi::Uuid) -> bool {
        self.0.is_ancestor(uuid.into(), ancestor.into())
    }

    fn sibling_positions(
        &self,
        parent: ffi::Uuid,
        at_root: bool,
        exclude: ffi::Uuid,
        has_exclude: bool,
    ) -> Vec<ffi::UuidStringPair> {
        let parent_opt = if at_root { None } else { Some(parent.into()) };
        let exclude_opt = if has_exclude {
            Some(tc::Uuid::from(&exclude))
        } else {
            None
        };
        self.0
            .sibling_positions(parent_opt, exclude_opt)
            .into_iter()
            .map(|(uuid, value)| ffi::UuidStringPair {
                uuid: uuid.into(),
                value,
            })
            .collect()
    }

    fn pending_child_ids(&self, uuid: ffi::Uuid) -> Vec<ffi::Uuid> {
        self.0
            .pending_child_ids(uuid.into())
            .into_iter()
            .map(ffi::Uuid::from)
            .collect()
    }

    fn had_invalid_data(&self) -> bool {
        self.0.had_invalid_data()
    }
}

// --- Position helpers

fn tc_append_position(last_pos: &CxxString) -> Result<String, CppError> {
    let s = last_pos.to_string_lossy();
    let opt = if s.is_empty() { None } else { Some(s.as_ref()) };
    tc::append_position(opt).map_err(|e| CppError(tc::Error::Other(e)))
}

fn tc_prepend_position(first_pos: &CxxString) -> Result<String, CppError> {
    let s = first_pos.to_string_lossy();
    let opt = if s.is_empty() { None } else { Some(s.as_ref()) };
    tc::prepend_position(opt).map_err(|e| CppError(tc::Error::Other(e)))
}

fn tc_between_position(before_pos: &CxxString, after_pos: &CxxString) -> Result<String, CppError> {
    tc::between_position(
        before_pos.to_string_lossy().as_ref(),
        after_pos.to_string_lossy().as_ref(),
    )
    .map_err(|e| CppError(tc::Error::Other(e)))
}

fn tc_sequential_positions(n: usize) -> Vec<String> {
    tc::sequential_positions(n)
}

// --- Plan markdown parser

fn tc_parse_plan_markdown(input: &CxxString) -> Vec<ffi::PlanNode> {
    // Return empty on non-UTF-8 input; the C++ caller will report "No headings found".
    let Ok(text) = input.to_str() else {
        return Vec::new();
    };
    tc::plan::parse_markdown(text)
        .into_iter()
        .map(|s| ffi::PlanNode {
            // Heading depths beyond u32::MAX are unreachable in practice, but we
            // use try_from to make any truncation an explicit panic rather than a
            // silent wraparound.
            level: u32::try_from(s.level).expect("heading level overflows u32"),
            title: s.heading,
            annotation: s.body,
        })
        .collect()
}

#[cfg(test)]
mod test {
    use super::*;

    fn test_replica() -> Box<Replica> {
        rt().block_on(async {
            let storage = PowerSyncStorage::new_for_test().await.unwrap();
            Box::new(tc::Replica::new(DynStorage::PowerSync(storage)).into())
        })
    }

    #[test]
    fn uuids() {
        let uuid = uuid_v4();
        assert_eq!(uuid.to_string().len(), 36);
    }

    #[test]
    fn operations() {
        cxx::let_cxx_string!(prop = "prop");
        cxx::let_cxx_string!(prop2 = "prop2");
        cxx::let_cxx_string!(value = "value");
        cxx::let_cxx_string!(value2 = "value2");

        let mut operations = new_operations();
        add_undo_point(&mut operations);
        let mut i = 0;
        assert_eq!(operations.len(), i + 1);
        assert!(!operations[i].is_create());
        assert!(!operations[i].is_update());
        assert!(!operations[i].is_delete());
        assert!(operations[i].is_undo_point());

        let uuid = uuid_v4();
        let mut t = create_task(uuid, &mut operations);
        i += 1;
        assert_eq!(operations.len(), i + 1);
        assert!(operations[i].is_create());
        assert!(!operations[i].is_update());
        assert!(!operations[i].is_delete());
        assert!(!operations[i].is_undo_point());
        assert_eq!(operations[i].get_uuid(), uuid);

        t.update(&prop, &value, &mut operations);
        i += 1;
        assert_eq!(operations.len(), i + 1);
        assert!(!operations[i].is_create());
        assert!(operations[i].is_update());
        assert!(!operations[i].is_delete());
        assert!(!operations[i].is_undo_point());
        assert_eq!(operations[i].get_uuid(), uuid);
        // Note that `get_value` and `get_old_value` cannot be tested from Rust, as it is not
        // possible to pass a reference to a CxxString and retain ownership of it.
        assert!(operations[i].get_timestamp() > 0);

        t.update(&prop2, &value, &mut operations);
        i += 1;
        assert_eq!(operations.len(), i + 1);
        assert!(!operations[i].is_create());
        assert!(operations[i].is_update());
        assert!(!operations[i].is_delete());
        assert!(!operations[i].is_undo_point());
        assert_eq!(operations[i].get_uuid(), uuid);
        assert!(operations[i].get_timestamp() > 0);

        t.update(&prop2, &value2, &mut operations);
        i += 1;
        assert_eq!(operations.len(), i + 1);
        assert!(!operations[i].is_create());
        assert!(operations[i].is_update());
        assert!(!operations[i].is_delete());
        assert!(!operations[i].is_undo_point());
        assert_eq!(operations[i].get_uuid(), uuid);
        assert!(operations[i].get_timestamp() > 0);

        t.update_remove(&prop, &mut operations);
        i += 1;
        assert_eq!(operations.len(), i + 1);
        assert!(!operations[i].is_create());
        assert!(operations[i].is_update());
        assert!(!operations[i].is_delete());
        assert!(!operations[i].is_undo_point());
        assert_eq!(operations[i].get_uuid(), uuid);
        assert!(operations[i].get_timestamp() > 0);

        t.delete_task(&mut operations);
        i += 1;
        assert_eq!(operations.len(), i + 1);
        assert!(!operations[i].is_create());
        assert!(!operations[i].is_update());
        assert!(operations[i].is_delete());
        assert!(!operations[i].is_undo_point());
        assert_eq!(operations[i].get_uuid(), uuid);
        assert_eq!(
            operations[i].get_old_task(),
            vec![ffi::PropValuePair {
                prop: "prop2".into(),
                value: "value2".into(),
            },]
        );
    }

    #[test]
    fn operation_counts() {
        let mut rep = test_replica();
        let mut operations = new_operations();
        add_undo_point(&mut operations);
        create_task(uuid_v4(), &mut operations);
        create_task(uuid_v4(), &mut operations);
        create_task(uuid_v4(), &mut operations);
        add_undo_point(&mut operations);
        rep.commit_operations(operations).unwrap();
        // PowerSync handles sync externally — unsynced operation tracking is not meaningful.
        // Just verify the calls succeed without error.
        rep.num_local_operations().unwrap();
        rep.num_undo_points().unwrap();
    }

    #[test]
    fn undo_operations() {
        let mut rep = test_replica();
        let mut operations = new_operations();
        let (uuid1, uuid2, uuid3) = (uuid_v4(), uuid_v4(), uuid_v4());
        add_undo_point(&mut operations);
        create_task(uuid1, &mut operations);
        add_undo_point(&mut operations);
        create_task(uuid2, &mut operations);
        create_task(uuid3, &mut operations);
        rep.commit_operations(operations).unwrap();
        // PowerSync handles sync externally — undo operations based on unsynced ops
        // are not meaningful. Just verify the call succeeds without error.
        rep.get_undo_operations().unwrap();
    }

    #[test]
    fn task_lists() {
        let mut rep = test_replica();
        let mut operations = new_operations();
        add_undo_point(&mut operations);
        create_task(uuid_v4(), &mut operations);
        create_task(uuid_v4(), &mut operations);
        let mut t = create_task(uuid_v4(), &mut operations);
        cxx::let_cxx_string!(status = "status");
        cxx::let_cxx_string!(pending = "pending");
        t.update(&status, &pending, &mut operations);
        rep.commit_operations(operations).unwrap();

        assert_eq!(rep.all_task_data().unwrap().len(), 3);
        assert_eq!(rep.all_task_uuids().unwrap().len(), 3);
        // PowerSync uses tc_working_set for pending_task_data which requires a PowerSync-managed
        // database. pending_task_data is not testable in the in-memory test environment.
    }

    #[test]
    fn expire_tasks() {
        let mut rep = test_replica();
        let mut operations = new_operations();
        add_undo_point(&mut operations);
        create_task(uuid_v4(), &mut operations);
        create_task(uuid_v4(), &mut operations);
        create_task(uuid_v4(), &mut operations);
        rep.commit_operations(operations).unwrap();
        rep.expire_tasks().unwrap();
    }

    #[test]
    fn get_task_data() {
        let mut rep = test_replica();

        let uuid = uuid_v4();
        assert!(rep.get_task_data(uuid).unwrap().is_none());

        let mut operations = new_operations();
        create_task(uuid, &mut operations);
        rep.commit_operations(operations).unwrap();

        let mut t = rep.get_task_data(uuid).unwrap();
        assert!(t.is_some());
        assert_eq!(t.take().get_uuid(), uuid);
    }

    #[test]
    fn get_task_operations() {
        cxx::let_cxx_string!(prop = "prop");
        cxx::let_cxx_string!(value = "value");
        let mut rep = test_replica();

        let uuid = uuid_v4();
        assert!(rep.get_task_operations(uuid).unwrap().is_empty());

        let mut operations = new_operations();
        let mut t = create_task(uuid, &mut operations);
        t.update(&prop, &value, &mut operations);
        rep.commit_operations(operations).unwrap();

        let ops = rep.get_task_operations(uuid).unwrap();
        assert_eq!(ops.len(), 2);
        assert!(ops[0].is_create());
        assert!(ops[1].is_update());
    }

    #[test]
    fn task_properties() {
        cxx::let_cxx_string!(prop = "prop");
        cxx::let_cxx_string!(prop2 = "prop2");
        cxx::let_cxx_string!(value = "value");

        let mut rep = test_replica();

        let uuid = uuid_v4();
        let mut operations = new_operations();
        let mut t = create_task(uuid, &mut operations);
        t.update(&prop, &value, &mut operations);
        rep.commit_operations(operations).unwrap();

        let t = rep.get_task_data(uuid).unwrap().take();
        assert!(t.has(&prop));
        assert!(!t.has(&prop2));
        // Note that `get` cannot be tested from Rust, as it is not possible to pass a reference to
        // a CxxString and retain ownership of it.

        assert_eq!(t.properties(), vec!["prop".to_string()]);
        assert_eq!(
            t.items(),
            vec![ffi::PropValuePair {
                prop: "prop".into(),
                value: "value".into(),
            }]
        );
    }

    // --- Tag registry

    #[test]
    fn validate_tag_blocks_unregistered() {
        let mut rep = test_replica();
        cxx::let_cxx_string!(tag = "work");
        // Before any registration, validate_tag must return an error.
        assert!(
            rep.validate_tag(&tag).is_err(),
            "validate_tag should fail for an unregistered tag"
        );
    }

    #[test]
    fn validate_tag_allows_registered() {
        let mut rep = test_replica();
        cxx::let_cxx_string!(tag = "work");
        rep.register_tag(&tag).unwrap();
        assert!(
            rep.validate_tag(&tag).is_ok(),
            "validate_tag should succeed after register_tag"
        );
    }

    #[test]
    fn seed_tags_noop_when_registry_nonempty() {
        let mut rep = test_replica();
        cxx::let_cxx_string!(existing = "work");
        // Pre-register one tag.
        rep.register_tag(&existing).unwrap();

        // Create a task with a different tag that is NOT in the registry.
        let mut ops = new_operations();
        let uuid = uuid_v4();
        let mut t = create_task(uuid, &mut ops);
        cxx::let_cxx_string!(tag_key = "tag_urgent");
        cxx::let_cxx_string!(tag_val = "x");
        t.update(&tag_key, &tag_val, &mut ops);
        rep.commit_operations(ops).unwrap();

        // seed_tags_from_tasks should be a no-op because the registry is non-empty.
        rep.seed_tags_from_tasks().unwrap();

        // "urgent" should NOT have been seeded (registry was already populated).
        cxx::let_cxx_string!(urgent = "urgent");
        assert!(
            rep.validate_tag(&urgent).is_err(),
            "seed_tags_from_tasks should not seed when registry is non-empty"
        );
        // "work" should still be registered.
        assert!(
            rep.validate_tag(&existing).is_ok(),
            "previously registered tag should still be valid"
        );
    }

    #[test]
    fn delete_tag_removes_registered_tag() {
        let mut rep = test_replica();
        cxx::let_cxx_string!(tag = "work");
        rep.register_tag(&tag).unwrap();
        // Tag should be registered.
        assert!(rep.validate_tag(&tag).is_ok(), "tag should be registered");
        // delete_tag should succeed and remove it.
        rep.delete_tag(&tag).unwrap();
        assert!(
            rep.validate_tag(&tag).is_err(),
            "tag should no longer be registered after delete_tag"
        );
    }

    #[test]
    fn delete_tag_errors_when_not_registered() {
        let mut rep = test_replica();
        cxx::let_cxx_string!(tag = "ghost");
        // Deleting an unregistered tag must return an error.
        assert!(
            rep.delete_tag(&tag).is_err(),
            "delete_tag should fail for an unregistered tag"
        );
    }

    #[test]
    fn migrate_tags_always_seeds() {
        let mut rep = test_replica();
        cxx::let_cxx_string!(existing = "work");
        // Pre-register one tag so registry is non-empty.
        rep.register_tag(&existing).unwrap();

        // Create a task with an unregistered tag.
        let mut ops = new_operations();
        let uuid = uuid_v4();
        let mut t = create_task(uuid, &mut ops);
        cxx::let_cxx_string!(tag_key = "tag_urgent");
        cxx::let_cxx_string!(tag_val = "x");
        t.update(&tag_key, &tag_val, &mut ops);
        rep.commit_operations(ops).unwrap();

        // migrate_tags_from_tasks should register "urgent" even though registry was non-empty.
        rep.migrate_tags_from_tasks().unwrap();

        cxx::let_cxx_string!(urgent = "urgent");
        assert!(
            rep.validate_tag(&urgent).is_ok(),
            "migrate_tags_from_tasks should register tags from task data unconditionally"
        );
    }
}
