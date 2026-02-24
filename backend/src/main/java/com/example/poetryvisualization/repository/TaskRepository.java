package com.example.poetryvisualization.repository;

import com.example.poetryvisualization.model.TaskAggregate;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Repository
public class TaskRepository {
  private final ConcurrentHashMap<String, TaskAggregate> store = new ConcurrentHashMap<>();

  public TaskAggregate save(TaskAggregate aggregate) {
    store.put(aggregate.getTaskId(), aggregate);
    return aggregate;
  }

  public Optional<TaskAggregate> findByTaskId(String taskId) {
    return Optional.ofNullable(store.get(taskId));
  }

  public Collection<TaskAggregate> findAll() {
    return store.values();
  }
}
